"""
Pydantic schemas for CA review workflow
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============== Transaction Review Schemas ==============

class TransactionCategoryUpdate(BaseModel):
    """Schema for updating transaction category"""
    category: str = Field(..., description="New category for the transaction")
    notes: Optional[str] = Field(None, description="CA's review notes")

class TransactionReviewResponse(BaseModel):
    """Schema for transaction review response"""
    id: int
    statement_id: int
    date: datetime
    description: str
    debit: float
    credit: float
    balance: float
    category: str
    manually_labeled: bool
    confidence_score: Optional[float]
    notes: Optional[str]
    is_tax_relevant: bool
    financial_year: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }

class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list"""
    total: int
    page: int
    page_size: int
    total_pages: int
    transactions: List[TransactionReviewResponse]


# ============== ITR Review Schemas ==============

class ITRReviewComment(BaseModel):
    """Schema for adding review comments to ITR"""
    comment: str = Field(..., min_length=1, max_length=2000, description="Review comment")
    comment_type: str = Field(
        default="general",
        pattern=r'^(general|discrepancy|suggestion|clarification)$',
        description="Type of comment"
    )

class ITRApproval(BaseModel):
    """Schema for CA approval of ITR"""
    approved: bool = Field(..., description="Approval status")
    ca_comments: Optional[str] = Field(None, max_length=2000, description="CA's final comments")
    suggestions: Optional[List[str]] = Field(None, description="List of suggestions for taxpayer")

class ITRReviewStatus(BaseModel):
    """Schema for ITR review status response"""
    id: int
    user_id: int
    assessment_year: str
    form_type: str
    status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    ca_comments: Optional[str] = None
    review_status: str  # pending_review, under_review, changes_requested, approved
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }


# ============== Review Assignment Schemas ==============

class ReviewAssignment(BaseModel):
    """Schema for assigning CA to user"""
    user_id: int = Field(..., description="User ID to assign")
    ca_id: int = Field(..., description="CA (reviewer) user ID")
    notes: Optional[str] = Field(None, description="Assignment notes")

class ReviewAssignmentResponse(BaseModel):
    """Schema for review assignment response"""
    id: int
    user_id: int
    ca_id: int
    assigned_at: datetime
    notes: Optional[str]
    is_active: bool
    
    model_config = {
        "from_attributes": True
    }


# ============== Audit Log Schemas ==============

class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    id: int
    user_id: Optional[int]
    action: str
    action_type: str
    description: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    entity_type: Optional[str]
    entity_id: Optional[int]
    status: str
    error_message: Optional[str]
    extra_data: Optional[str]
    timestamp: datetime
    
    model_config = {
        "from_attributes": True
    }

class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list"""
    total: int
    page: int
    page_size: int
    total_pages: int
    logs: List[AuditLogResponse]


# ============== Review Summary Schemas ==============

class ReviewSummary(BaseModel):
    """Schema for review summary statistics"""
    total_transactions: int
    reviewed_transactions: int
    pending_review: int
    tax_relevant_transactions: int
    total_income: float
    total_deductions: float
    categories_breakdown: dict
    review_progress_percentage: float

class CADashboard(BaseModel):
    """Schema for CA dashboard data"""
    assigned_users: int
    pending_reviews: int
    approved_itrs: int
    total_transactions_reviewed: int
    recent_activity: List[dict]
