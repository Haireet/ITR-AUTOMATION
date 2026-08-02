"""
Consolidation Router — merge bank statements & auto-calculate ITR
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from database import get_db
from models import User
from utils.security import get_current_user
from services.consolidation_service import ConsolidationService
from schemas.consolidation_schemas import (
    MergeStatementsRequest,
    CalculateTaxRequest,
    CreateFilingFromMergeRequest,
)

router = APIRouter()


@router.post("/merge", summary="Merge multiple bank statements")
async def merge_statements(
    req: MergeStatementsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Merge transactions from selected bank statements for a financial year.
    Deduplicates overlapping transactions and returns categorised summary.
    """
    result = ConsolidationService.merge_transactions(
        db, current_user.id, req.statement_ids, req.financial_year
    )
    if result["statements_merged"] == 0:
        raise HTTPException(status_code=404, detail="No processed statements found for the given IDs")
    return result


@router.post("/calculate-tax", summary="Calculate tax from merged statements")
async def calculate_tax(
    req: CalculateTaxRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calculate income tax from merged bank statement data.
    Supports old regime, new regime, or both (comparison).
    """
    result = ConsolidationService.calculate_tax(
        db, current_user.id, req.financial_year, req.tax_regime, req.statement_ids
    )
    return result


@router.post("/create-filing", summary="Create ITR filing from merged data")
async def create_filing_from_merge(
    req: CreateFilingFromMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a draft ITR filing with auto-computed tax from merged statements.
    """
    try:
        result = ConsolidationService.create_filing_from_merge(
            db, current_user.id,
            req.financial_year, req.tax_regime, req.form_type, req.statement_ids
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary/{financial_year}", summary="Get merged summary for a FY")
async def get_merged_summary(
    financial_year: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get consolidated summary of all processed statements for a financial year."""
    result = ConsolidationService.merge_transactions(
        db, current_user.id, statement_ids=None, financial_year=financial_year
    )
    return result
