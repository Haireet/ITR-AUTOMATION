"""
Balance Sheet router - handles balance sheet CRUD and auto-generation
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List

from database import get_db
from utils.security import get_current_user
from models import User
from schemas.balance_sheet_schemas import (
    BalanceSheetCreate, BalanceSheetUpdate,
    BalanceSheetResponse, BalanceSheetListResponse,
    BalanceSheetItemCreate, BalanceSheetItemUpdate,
    BalanceSheetItemResponse, BalanceSheetSummary,
)
from services.balance_sheet_service import BalanceSheetService

router = APIRouter()


# ---- Balance Sheet CRUD ----

@router.post("/", response_model=BalanceSheetResponse, status_code=status.HTTP_201_CREATED)
async def create_balance_sheet(
    data: BalanceSheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new balance sheet (Schedule AL / Personal / Business)"""
    return BalanceSheetService.create_balance_sheet(db, current_user.id, data)


@router.get("/", response_model=BalanceSheetListResponse)
async def list_balance_sheets(
    sheet_type: Optional[str] = Query(None, pattern=r'^(schedule_al|personal|business)$'),
    financial_year: Optional[str] = Query(None, pattern=r'^\d{4}-\d{2}$'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List balance sheets for the current user"""
    sheets = BalanceSheetService.get_balance_sheets(db, current_user.id, sheet_type, financial_year)
    return BalanceSheetListResponse(balance_sheets=sheets, total=len(sheets))


@router.get("/summary", response_model=BalanceSheetSummary)
async def get_transaction_summary(
    financial_year: str = Query(..., pattern=r'^\d{4}-\d{2}$'),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Auto-generate personal balance sheet summary from transactions"""
    return BalanceSheetService.generate_summary_from_transactions(db, current_user.id, financial_year)


@router.get("/{bs_id}", response_model=BalanceSheetResponse)
async def get_balance_sheet(
    bs_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific balance sheet by ID"""
    return BalanceSheetService.get_balance_sheet(db, bs_id, current_user.id)


@router.put("/{bs_id}", response_model=BalanceSheetResponse)
async def update_balance_sheet(
    bs_id: int,
    data: BalanceSheetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update balance sheet metadata"""
    return BalanceSheetService.update_balance_sheet(db, bs_id, current_user.id, data)


@router.delete("/{bs_id}")
async def delete_balance_sheet(
    bs_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a balance sheet"""
    BalanceSheetService.delete_balance_sheet(db, bs_id, current_user.id)
    return {"message": "Balance sheet deleted"}


# ---- Item CRUD ----

@router.post("/{bs_id}/items", response_model=BalanceSheetItemResponse, status_code=status.HTTP_201_CREATED)
async def add_item(
    bs_id: int,
    data: BalanceSheetItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add an item to a balance sheet"""
    return BalanceSheetService.add_item(db, bs_id, current_user.id, data)


@router.put("/items/{item_id}", response_model=BalanceSheetItemResponse)
async def update_item(
    item_id: int,
    data: BalanceSheetItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a balance sheet item"""
    return BalanceSheetService.update_item(db, item_id, current_user.id, data)


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a balance sheet item"""
    BalanceSheetService.delete_item(db, item_id, current_user.id)
    return {"message": "Item deleted"}
