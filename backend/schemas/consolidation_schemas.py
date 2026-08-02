"""
Pydantic schemas for statement consolidation and tax calculation
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MergeStatementsRequest(BaseModel):
    """Request to merge multiple bank statements"""
    statement_ids: List[int] = Field(..., min_length=1, description="IDs of statements to merge")
    financial_year: str = Field(..., pattern=r'^\d{4}-\d{2}$', description="Financial year e.g. 2024-25")


class CategorySummary(BaseModel):
    """Summary of transactions in a category"""
    category: str
    transaction_count: int
    total_credit: float
    total_debit: float
    net_amount: float


class MergedSummary(BaseModel):
    """Result of merging statements"""
    financial_year: str
    statements_merged: int
    total_transactions: int
    duplicates_removed: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    total_credit: float
    total_debit: float
    net_balance: float
    category_breakdown: List[CategorySummary]


class TaxSlabDetail(BaseModel):
    """Detail of a single tax slab"""
    slab: str
    rate: str
    taxable_amount: float
    tax: float


class TaxCalculationResult(BaseModel):
    """Full tax calculation result"""
    financial_year: str
    assessment_year: str
    tax_regime: str

    # Income
    salary_income: float = 0
    interest_income: float = 0
    dividend_income: float = 0
    rental_income: float = 0
    capital_gains: float = 0
    business_income: float = 0
    other_income: float = 0
    gross_total_income: float = 0

    # Deductions
    deduction_80c: float = 0
    deduction_80d: float = 0
    home_loan_interest: float = 0
    donations: float = 0
    total_deductions: float = 0

    # Tax
    taxable_income: float = 0
    slab_details: List[TaxSlabDetail] = []
    tax_before_cess: float = 0
    rebate_87a: float = 0
    tax_after_rebate: float = 0
    health_education_cess: float = 0
    total_tax_liability: float = 0

    # Comparison (filled when both regimes computed)
    recommended_regime: Optional[str] = None
    old_regime_tax: Optional[float] = None
    new_regime_tax: Optional[float] = None
    savings: Optional[float] = None


class CalculateTaxRequest(BaseModel):
    """Request to calculate tax from merged statements"""
    financial_year: str = Field(..., pattern=r'^\d{4}-\d{2}$')
    tax_regime: str = Field(default="both", pattern=r'^(old|new|both)$')
    statement_ids: Optional[List[int]] = Field(None, description="Specific statements; if null, uses all")


class CreateFilingFromMergeRequest(BaseModel):
    """Request to create ITR filing from merged/calculated data"""
    financial_year: str = Field(..., pattern=r'^\d{4}-\d{2}$')
    tax_regime: str = Field(default="new", pattern=r'^(old|new)$')
    form_type: str = Field(default="ITR-1", pattern=r'^ITR-[1-7]$')
    statement_ids: Optional[List[int]] = None
