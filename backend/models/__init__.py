"""
SQLAlchemy Database Models for Auto ITR
Handles user authentication, bank statements, transactions, and audit logging
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum

# ============== Enums ==============

class UserRole(str, enum.Enum):
    """User role enumeration"""
    USER = "user"           # Regular user
    ADMIN = "admin"         # Administrator
    AUDITOR = "auditor"     # Read-only auditor access

class TransactionCategory(str, enum.Enum):
    """Transaction category for tax classification"""
    SALARY = "salary"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    CAPITAL_GAINS = "capital_gains"
    RENTAL_INCOME = "rental_income"
    BUSINESS_INCOME = "business_income"
    DEDUCTION_80C = "deduction_80c"
    DEDUCTION_80D = "deduction_80d"
    HOME_LOAN_INTEREST = "home_loan_interest"
    DONATION = "donation"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    UNCATEGORIZED = "uncategorized"

# ============== Models ==============

class User(Base):
    """
    User model for authentication and authorization
    Stores user credentials and profile information
    """
    __tablename__ = "users"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Authentication fields
    email = Column(String(255), unique=True, index=True, nullable=False, comment="User email address (unique)")
    password_hash = Column(String(255), nullable=False, comment="Bcrypt hashed password")
    
    # Role and status
    role = Column(
        Enum(UserRole), 
        nullable=False, 
        default=UserRole.USER,
        comment="User role: user, admin, or auditor"
    )
    is_active = Column(Boolean, default=True, nullable=False, comment="Account active status")
    is_verified = Column(Boolean, default=False, nullable=False, comment="Email verification status")
    
    # Profile information
    full_name = Column(String(100), nullable=True, comment="User full name")
    pan_number = Column(String(10), unique=True, index=True, nullable=True, comment="PAN card number (unique)")
    phone_number = Column(String(15), nullable=True, comment="Contact phone number")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Account creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last update timestamp")
    last_login = Column(DateTime, nullable=True, comment="Last successful login timestamp")
    
    # Relationships
    bank_statements = relationship(
        "BankStatement",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    itr_filings = relationship(
        "ITRFiling",
        foreign_keys="ITRFiling.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    reviewed_filings = relationship(
        "ITRFiling",
        foreign_keys="ITRFiling.reviewed_by",
        back_populates="reviewer",
        lazy="dynamic"
    )
    approved_filings = relationship(
        "ITRFiling",
        foreign_keys="ITRFiling.approved_by",
        back_populates="approver",
        lazy="dynamic"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"


class BankStatement(Base):
    """
    Bank statement model
    Stores uploaded bank statement files and metadata
    """
    __tablename__ = "bank_statements"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="Reference to user who uploaded the statement"
    )
    
    # File information
    filename = Column(String(255), nullable=False, comment="Original filename of uploaded statement")
    file_path = Column(String(500), nullable=True, comment="Server storage path (if storing files)")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_type = Column(String(50), nullable=True, comment="MIME type or file extension")
    
    # Statement metadata
    bank_name = Column(String(100), nullable=True, comment="Name of the bank")
    account_number = Column(String(50), nullable=True, comment="Bank account number (last 4 digits)")
    statement_period_start = Column(DateTime, nullable=True, comment="Statement period start date")
    statement_period_end = Column(DateTime, nullable=True, comment="Statement period end date")
    
    # Processing status
    is_processed = Column(Boolean, default=False, nullable=False, comment="Whether transactions have been extracted")
    processing_status = Column(String(50), default="pending", nullable=False, comment="pending, processing, completed, failed")
    error_message = Column(Text, nullable=True, comment="Error message if processing failed")
    
    # Timestamps
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Upload timestamp")
    processed_date = Column(DateTime, nullable=True, comment="Processing completion timestamp")
    
    # Relationships
    user = relationship("User", back_populates="bank_statements")
    transactions = relationship(
        "Transaction", 
        back_populates="statement", 
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self):
        return f"<BankStatement(id={self.id}, user_id={self.user_id}, filename={self.filename})>"


class Transaction(Base):
    """
    Transaction model
    Stores individual bank transactions extracted from statements
    Used for income categorization and tax computation
    """
    __tablename__ = "transactions"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key
    statement_id = Column(
        Integer, 
        ForeignKey("bank_statements.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="Reference to source bank statement"
    )
    
    # Transaction details
    date = Column(DateTime, nullable=False, index=True, comment="Transaction date")
    description = Column(Text, nullable=False, comment="Transaction description/narration")
    
    # Financial amounts
    debit = Column(Float, nullable=True, default=0.0, comment="Debit amount (money out)")
    credit = Column(Float, nullable=True, default=0.0, comment="Credit amount (money in)")
    balance = Column(Float, nullable=True, comment="Account balance after transaction")
    
    # Categorization
    category = Column(
        Enum(TransactionCategory), 
        nullable=False, 
        default=TransactionCategory.UNCATEGORIZED,
        index=True,
        comment="Tax-relevant category"
    )
    manually_labeled = Column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="True if user manually categorized, False if auto-categorized"
    )
    confidence_score = Column(
        Float, 
        nullable=True,
        comment="ML model confidence score for auto-categorization (0.0-1.0)"
    )
    
    # Additional metadata
    reference_number = Column(String(100), nullable=True, comment="Transaction reference/check number")
    notes = Column(Text, nullable=True, comment="User-added notes")
    
    # Tax relevance
    is_tax_relevant = Column(Boolean, default=True, nullable=False, comment="Whether transaction affects tax computation")
    financial_year = Column(String(10), nullable=True, index=True, comment="Financial year (e.g., 2024-25)")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Record creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last update timestamp")
    
    # Relationships
    statement = relationship("BankStatement", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, date={self.date}, category={self.category}, amount={self.credit or self.debit})>"


class AuditLog(Base):
    """
    Audit log model
    Tracks all significant user actions for compliance and security
    """
    __tablename__ = "audit_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="Reference to user who performed the action"
    )
    
    # Action details
    action = Column(String(100), nullable=False, index=True, comment="Action performed (e.g., 'login', 'upload_statement', 'file_itr')")
    action_type = Column(String(50), nullable=False, comment="Type: authentication, data_access, data_modification, file_operation")
    description = Column(Text, nullable=True, comment="Detailed description of the action")
    
    # Context information
    ip_address = Column(String(45), nullable=True, comment="IP address of the user (IPv4 or IPv6)")
    user_agent = Column(String(500), nullable=True, comment="Browser/client user agent string")
    
    # Entity references
    entity_type = Column(String(50), nullable=True, comment="Type of entity affected (e.g., 'bank_statement', 'transaction')")
    entity_id = Column(Integer, nullable=True, comment="ID of the affected entity")
    
    # Status and result
    status = Column(String(20), nullable=False, default="success", comment="success, failed, warning")
    error_message = Column(Text, nullable=True, comment="Error message if action failed")
    
    # Additional metadata
    extra_data = Column(Text, nullable=True, comment="JSON string with additional context")
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="Action timestamp")
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action={self.action}, timestamp={self.timestamp})>"


class ITRFiling(Base):
    """
    ITR Filing model - stores tax return submissions
    Retained from original schema for backward compatibility
    """
    __tablename__ = "itr_filings"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key
    user_id = Column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True,
        comment="Reference to user filing the return"
    )
    
    # Filing details
    assessment_year = Column(String(10), nullable=False, index=True, comment="Assessment year (e.g., 2024-25)")
    form_type = Column(String(10), nullable=False, comment="ITR form type (e.g., ITR-1, ITR-2)")
    status = Column(String(20), default="draft", nullable=False, comment="draft, completed, filed, acknowledged")
    
    # Data storage
    data = Column(Text, nullable=True, comment="JSON string of complete form data")
    
    # Filing information
    filing_date = Column(DateTime, nullable=True, comment="Date when ITR was filed")
    acknowledgement_number = Column(String(50), nullable=True, unique=True, comment="IT Department acknowledgement number")
    
    # Review fields
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="CA who reviewed this filing")
    reviewed_at = Column(DateTime, nullable=True, comment="Review timestamp")
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="CA who approved this filing")
    approved_at = Column(DateTime, nullable=True, comment="Approval timestamp")
    ca_comments = Column(Text, nullable=True, comment="CA's review comments")
    review_status = Column(String(20), default="pending_review", nullable=False, comment="pending_review, pending_ca_approval, under_review, changes_requested, approved")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Draft creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last update timestamp")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="itr_filings")
    reviewer = relationship("User", foreign_keys=[reviewed_by], back_populates="reviewed_filings")
    approver = relationship("User", foreign_keys=[approved_by], back_populates="approved_filings")
    tax_computations = relationship(
        "TaxComputation",
        back_populates="itr_filing",
        cascade="all, delete-orphan",
        uselist=False
    )
    
    def __repr__(self):
        return f"<ITRFiling(id={self.id}, user_id={self.user_id}, assessment_year={self.assessment_year}, status={self.status})>"


class BalanceSheetType(str, enum.Enum):
    """Balance sheet type enumeration"""
    SCHEDULE_AL = "schedule_al"   # Schedule AL for ITR-3/ITR-4
    PERSONAL = "personal"         # Personal financial balance sheet
    BUSINESS = "business"         # Business balance sheet

class BalanceSheetItemType(str, enum.Enum):
    """Balance sheet item side"""
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"


class BalanceSheet(Base):
    """
    Balance sheet model
    Supports Schedule AL, Personal, and Business balance sheets
    """
    __tablename__ = "balance_sheets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to owner user"
    )
    sheet_type = Column(
        Enum(BalanceSheetType),
        nullable=False,
        index=True,
        comment="Type: schedule_al, personal, business"
    )
    financial_year = Column(String(10), nullable=False, index=True, comment="Financial year e.g. 2024-25")
    name = Column(String(200), nullable=True, comment="Optional label")
    total_assets = Column(Float, default=0.0, nullable=False)
    total_liabilities = Column(Float, default=0.0, nullable=False)
    total_equity = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", backref="balance_sheets")
    items = relationship(
        "BalanceSheetItem",
        back_populates="balance_sheet",
        cascade="all, delete-orphan",
        lazy="joined"
    )

    def __repr__(self):
        return f"<BalanceSheet(id={self.id}, type={self.sheet_type}, fy={self.financial_year})>"


class BalanceSheetItem(Base):
    """
    Individual line item in a balance sheet
    """
    __tablename__ = "balance_sheet_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    balance_sheet_id = Column(
        Integer,
        ForeignKey("balance_sheets.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    item_type = Column(
        Enum(BalanceSheetItemType),
        nullable=False,
        index=True,
        comment="asset, liability, or equity"
    )
    category = Column(String(100), nullable=False, comment="Category e.g. Immovable Property, Bank Deposits")
    subcategory = Column(String(100), nullable=True, comment="Subcategory e.g. Land, Building")
    description = Column(Text, nullable=True, comment="Item description")
    amount = Column(Float, default=0.0, nullable=False, comment="Item value in INR")
    as_on_date = Column(DateTime, nullable=True, comment="Valuation date")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    balance_sheet = relationship("BalanceSheet", back_populates="items")

    def __repr__(self):
        return f"<BalanceSheetItem(id={self.id}, type={self.item_type}, amount={self.amount})>"


class TaxComputation(Base):
    """
    Tax computation results
    Stores calculated tax amounts for an ITR filing
    """
    __tablename__ = "tax_computations"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Foreign key
    itr_filing_id = Column(
        Integer, 
        ForeignKey("itr_filings.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True,
        comment="Reference to ITR filing (one-to-one relationship)"
    )
    
    # Income details
    gross_total_income = Column(Float, default=0.0, nullable=False, comment="Total income before deductions")
    total_deductions = Column(Float, default=0.0, nullable=False, comment="Total deductions (80C, 80D, etc.)")
    taxable_income = Column(Float, default=0.0, nullable=False, comment="Income after deductions")
    
    # Tax calculation
    tax_on_total_income = Column(Float, default=0.0, nullable=False, comment="Tax before rebate and cess")
    rebate_87a = Column(Float, default=0.0, nullable=False, comment="Rebate under section 87A")
    health_education_cess = Column(Float, default=0.0, nullable=False, comment="4% cess on tax")
    total_tax_liability = Column(Float, default=0.0, nullable=False, comment="Final tax payable")
    
    # Tax regime
    tax_regime = Column(String(10), default="old", nullable=False, comment="Tax regime: 'old' or 'new'")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="Computation creation timestamp")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last update timestamp")
    
    # Relationships
    itr_filing = relationship("ITRFiling", back_populates="tax_computations")
    
    def __repr__(self):
        return f"<TaxComputation(id={self.id}, itr_filing_id={self.itr_filing_id}, total_tax={self.total_tax_liability})>"