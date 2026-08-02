"""
Export router - handles PDF and JSON export of ITR, Balance Sheet, Transactions
"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from database import get_db
from models import User
from utils.security import get_current_user
from services.export_service import ExportService

router = APIRouter()


def _pdf_response(pdf_data, filename: str) -> Response:
    """Helper to return PDF bytes as a proper Response"""
    return Response(
        content=bytes(pdf_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── ITR Exports ──────────────────────────────────────────────────────────

@router.get("/itr/{filing_id}/pdf")
async def export_itr_pdf(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export ITR filing as PDF"""
    pdf_bytes = ExportService.export_itr_pdf(db, filing_id, current_user.id)
    return _pdf_response(pdf_bytes, f"ITR_{filing_id}.pdf")


@router.get("/itr/{filing_id}/json")
async def export_itr_json(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export ITR filing as JSON"""
    data = ExportService.export_itr_json(db, filing_id, current_user.id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=ITR_{filing_id}.json"},
    )


# ─── Balance Sheet Exports ────────────────────────────────────────────────

@router.get("/balance-sheet/{bs_id}/pdf")
async def export_balance_sheet_pdf(
    bs_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export balance sheet as PDF"""
    pdf_bytes = ExportService.export_balance_sheet_pdf(db, bs_id, current_user.id)
    return _pdf_response(pdf_bytes, f"BalanceSheet_{bs_id}.pdf")


@router.get("/balance-sheet/{bs_id}/json")
async def export_balance_sheet_json(
    bs_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export balance sheet as JSON"""
    data = ExportService.export_balance_sheet_json(db, bs_id, current_user.id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=BalanceSheet_{bs_id}.json"},
    )


# ─── Transaction Exports ─────────────────────────────────────────────────

@router.get("/transactions/{statement_id}/pdf")
async def export_transactions_pdf(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as PDF"""
    pdf_bytes = ExportService.export_transactions_pdf(db, statement_id, current_user.id)
    return _pdf_response(pdf_bytes, f"Transactions_{statement_id}.pdf")


@router.get("/transactions/{statement_id}/json")
async def export_transactions_json(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export transactions as JSON"""
    data = ExportService.export_transactions_json(db, statement_id, current_user.id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=Transactions_{statement_id}.json"},
    )


# ─── Merged Statement Exports ────────────────────────────────────────────

@router.post("/merged/pdf")
async def export_merged_pdf(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export merged/consolidated statement as PDF"""
    statement_ids = request.get("statement_ids", [])
    financial_year = request.get("financial_year", "2024-25")
    pdf_bytes = ExportService.export_merged_pdf(db, current_user.id, statement_ids, financial_year)
    return _pdf_response(pdf_bytes, f"Merged_Statement_{financial_year}.pdf")


@router.post("/merged/json")
async def export_merged_json(
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export merged/consolidated statement as JSON"""
    statement_ids = request.get("statement_ids", [])
    financial_year = request.get("financial_year", "2024-25")
    data = ExportService.export_merged_json(db, current_user.id, statement_ids, financial_year)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=Merged_Statement_{financial_year}.json"},
    )
