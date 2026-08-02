"""
Pydantic schemas for Balance Sheet feature
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============== Balance Sheet Item Schemas ==============

class BalanceSheetItemCreate(BaseModel):
    """Schema for creating a balance sheet item"""
    item_type: str = Field(..., pattern=r'^(asset|liability|equity)$', description="asset, liability, or equity")
    category: str = Field(..., min_length=1, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    amount: float = Field(default=0.0, ge=0)
    as_on_date: Optional[datetime] = None


class BalanceSheetItemUpdate(BaseModel):
    """Schema for updating a balance sheet item"""
    item_type: Optional[str] = Field(None, pattern=r'^(asset|liability|equity)$')
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    subcategory: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    amount: Optional[float] = Field(None, ge=0)
    as_on_date: Optional[datetime] = None


class BalanceSheetItemResponse(BaseModel):
    """Schema for balance sheet item response"""
    id: int
    balance_sheet_id: int
    item_type: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    amount: float
    as_on_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============== Balance Sheet Schemas ==============

class BalanceSheetCreate(BaseModel):
    """Schema for creating a balance sheet"""
    sheet_type: str = Field(..., pattern=r'^(schedule_al|personal|business)$')
    financial_year: str = Field(..., pattern=r'^\d{4}-\d{2}$', description="e.g. 2024-25")
    name: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None
    items: Optional[List[BalanceSheetItemCreate]] = []


class BalanceSheetUpdate(BaseModel):
    """Schema for updating a balance sheet"""
    name: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class BalanceSheetResponse(BaseModel):
    """Schema for balance sheet response"""
    id: int
    user_id: int
    sheet_type: str
    financial_year: str
    name: Optional[str] = None
    total_assets: float
    total_liabilities: float
    total_equity: float
    notes: Optional[str] = None
    items: List[BalanceSheetItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BalanceSheetListResponse(BaseModel):
    """Schema for listing balance sheets"""
    balance_sheets: List[BalanceSheetResponse]
    total: int


class BalanceSheetSummary(BaseModel):
    """Auto-generated summary from transactions"""
    financial_year: str
    total_income: float = 0.0
    total_expenses: float = 0.0
    income_breakdown: dict = {}
    expense_breakdown: dict = {}
    net_worth: float = 0.0
