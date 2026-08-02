"""
ITR router - handles ITR filing operations
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User
from utils.security import get_current_user
from schemas import (
    ITRFilingCreate,
    ITRFilingUpdate,
    ITRFilingResponse,
    TaxComputationCreate,
    TaxComputationResponse,
    MessageResponse
)
from services.itr_service import ITRService, TaxComputationService

router = APIRouter()


@router.post("/filings", response_model=ITRFilingResponse, status_code=status.HTTP_201_CREATED)
async def create_itr_filing(
    filing_data: ITRFilingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new ITR filing draft"""
    return ITRService.create_filing(db, current_user.id, filing_data)


@router.get("/filings", response_model=List[ITRFilingResponse])
async def get_user_filings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all ITR filings for current user"""
    return ITRService.get_user_filings(db, current_user.id)


@router.get("/filings/{filing_id}", response_model=ITRFilingResponse)
async def get_filing(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get specific ITR filing by ID"""
    return ITRService.get_filing_by_id(db, filing_id, current_user.id)


@router.put("/filings/{filing_id}", response_model=ITRFilingResponse)
async def update_filing(
    filing_id: int,
    filing_data: ITRFilingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update ITR filing data"""
    return ITRService.update_filing(db, filing_id, current_user.id, filing_data)


@router.delete("/filings/{filing_id}", response_model=MessageResponse)
async def delete_filing(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete ITR filing draft"""
    ITRService.delete_filing(db, filing_id, current_user.id)
    return MessageResponse(message="ITR filing deleted")


@router.post("/filings/{filing_id}/submit-review", response_model=ITRFilingResponse)
async def submit_for_review(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit ITR filing for CA review (required before filing)"""
    return ITRService.submit_for_review(db, filing_id, current_user.id)


@router.post("/filings/{filing_id}/file", response_model=ITRFilingResponse)
async def file_itr(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """File ITR (only allowed after CA approval)"""
    return ITRService.file_itr(db, filing_id, current_user.id)


@router.post("/computations", response_model=TaxComputationResponse, status_code=status.HTTP_201_CREATED)
async def create_tax_computation(
    computation_data: TaxComputationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create/update tax computation for a filing"""
    return TaxComputationService.create_or_update_computation(
        db, computation_data.itr_filing_id, current_user.id, computation_data
    )


@router.get("/computations/{filing_id}", response_model=TaxComputationResponse)
async def get_tax_computation(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get tax computation for a specific filing"""
    return TaxComputationService.get_computation_by_filing(db, filing_id)
