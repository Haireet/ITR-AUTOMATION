"""
Pydantic schemas for bank statement operations
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ============== Bank Statement Schemas ==============

class BankStatementResponse(BaseModel):
    """Schema for bank statement response"""
    id: int
    user_id: int
    filename: str
    file_path: Optional[str] = None
    file_size: int
    file_type: str
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    statement_period_start: Optional[datetime] = None
    statement_period_end: Optional[datetime] = None
    is_processed: bool
    processing_status: str
    error_message: Optional[str] = None
    upload_date: datetime
    processed_date: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True
    }

class BankStatementUploadResponse(BaseModel):
    """Schema for successful upload response"""
    message: str = Field(..., description="Success message")
    statement: BankStatementResponse
    detail: Optional[str] = Field(None, description="Additional details")

class BankStatementListResponse(BaseModel):
    """Schema for listing bank statements"""
    total: int
    statements: list[BankStatementResponse]


# ============== Transaction Schemas ==============

class TransactionResponse(BaseModel):
    """Schema for a single transaction"""
    id: int
    statement_id: int
    date: datetime
    description: str
    debit: float
    credit: float
    balance: Optional[float] = None
    category: str
    manually_labeled: bool
    confidence_score: Optional[float] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None
    is_tax_relevant: bool
    financial_year: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionUpdateRequest(BaseModel):
    """Schema for manually updating a transaction's category"""
    category: str = Field(..., description="New category for the transaction")
    notes: Optional[str] = Field(None, description="Optional notes")


class TransactionListResponse(BaseModel):
    """Schema for listing transactions of a statement"""
    total: int
    statement_id: int
    transactions: List[TransactionResponse]


# ============== Process Statement Schemas ==============

class ProcessStatementResponse(BaseModel):
    """Schema for statement processing result"""
    message: str
    statement_id: int
    transactions_extracted: int
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    statement_period_start: Optional[datetime] = None
    statement_period_end: Optional[datetime] = None
    warnings: List[str] = Field(default_factory=list)
    processing_status: str
