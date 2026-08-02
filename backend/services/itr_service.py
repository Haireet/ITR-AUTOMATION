"""
ITR service - business logic for ITR operations
"""
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from models import ITRFiling, TaxComputation, AuditLog
from schemas import ITRFilingCreate, ITRFilingUpdate, TaxComputationCreate
from typing import List, Optional


class ITRService:
    """Service class for ITR filing operations"""

    @staticmethod
    def create_filing(db: Session, user_id: int, filing_data: ITRFilingCreate) -> ITRFiling:
        """Create new ITR filing draft"""
        filing = ITRFiling(
            user_id=user_id,
            assessment_year=filing_data.assessment_year,
            form_type=filing_data.form_type,
            data=filing_data.data,
            status="draft",
            review_status="pending_review",
        )
        db.add(filing)
        db.commit()
        db.refresh(filing)
        return filing

    @staticmethod
    def get_user_filings(db: Session, user_id: int) -> List[ITRFiling]:
        """Get all filings for a user"""
        return (
            db.query(ITRFiling)
            .filter(ITRFiling.user_id == user_id)
            .order_by(ITRFiling.updated_at.desc())
            .all()
        )

    @staticmethod
    def get_filing_by_id(db: Session, filing_id: int, user_id: int) -> ITRFiling:
        """Get specific filing by ID with ownership check"""
        filing = (
            db.query(ITRFiling)
            .filter(ITRFiling.id == filing_id, ITRFiling.user_id == user_id)
            .first()
        )
        if not filing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ITR filing not found")
        return filing

    @staticmethod
    def update_filing(db: Session, filing_id: int, user_id: int, filing_data: ITRFilingUpdate) -> ITRFiling:
        """Update filing data (only if not yet approved/filed)"""
        filing = ITRService.get_filing_by_id(db, filing_id, user_id)
        if filing.status in ("filed", "acknowledged"):
            raise HTTPException(status_code=400, detail="Cannot update a filed/acknowledged ITR")
        if filing_data.data is not None:
            filing.data = filing_data.data
        if filing_data.status is not None:
            filing.status = filing_data.status
        if filing_data.acknowledgement_number is not None:
            filing.acknowledgement_number = filing_data.acknowledgement_number
        filing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(filing)
        return filing

    @staticmethod
    def delete_filing(db: Session, filing_id: int, user_id: int) -> bool:
        """Delete filing draft"""
        filing = ITRService.get_filing_by_id(db, filing_id, user_id)
        if filing.status in ("filed", "acknowledged"):
            raise HTTPException(status_code=400, detail="Cannot delete a filed/acknowledged ITR")
        db.delete(filing)
        db.commit()
        return True

    @staticmethod
    def submit_for_review(db: Session, filing_id: int, user_id: int) -> ITRFiling:
        """Submit ITR filing for CA review"""
        filing = ITRService.get_filing_by_id(db, filing_id, user_id)
        if filing.review_status not in ("pending_review", "changes_requested"):
            raise HTTPException(status_code=400, detail=f"Cannot submit for review: current status is {filing.review_status}")
        filing.status = "completed"
        filing.review_status = "pending_ca_approval"
        filing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(filing)
        return filing

    @staticmethod
    def file_itr(db: Session, filing_id: int, user_id: int) -> ITRFiling:
        """File ITR (only allowed after CA approval)"""
        filing = ITRService.get_filing_by_id(db, filing_id, user_id)
        if filing.review_status != "approved":
            raise HTTPException(
                status_code=400,
                detail="ITR can only be filed after CA approval. Current review status: " + filing.review_status
            )
        filing.status = "filed"
        filing.filing_date = datetime.utcnow()
        filing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(filing)
        return filing


class TaxComputationService:
    """Service class for tax computation operations"""

    @staticmethod
    def create_or_update_computation(db: Session, filing_id: int, user_id: int,
                                     computation_data: TaxComputationCreate) -> TaxComputation:
        """Create or update tax computation for a filing"""
        # Verify filing ownership
        filing = ITRService.get_filing_by_id(db, filing_id, user_id)

        existing = db.query(TaxComputation).filter(TaxComputation.itr_filing_id == filing.id).first()
        if existing:
            for field in ['gross_total_income', 'total_deductions', 'taxable_income',
                          'tax_on_total_income', 'rebate_87a', 'health_education_cess',
                          'total_tax_liability', 'tax_regime']:
                setattr(existing, field, getattr(computation_data, field))
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

        comp = TaxComputation(
            itr_filing_id=filing.id,
            gross_total_income=computation_data.gross_total_income,
            total_deductions=computation_data.total_deductions,
            taxable_income=computation_data.taxable_income,
            tax_on_total_income=computation_data.tax_on_total_income,
            rebate_87a=computation_data.rebate_87a,
            health_education_cess=computation_data.health_education_cess,
            total_tax_liability=computation_data.total_tax_liability,
            tax_regime=computation_data.tax_regime,
        )
        db.add(comp)
        db.commit()
        db.refresh(comp)
        return comp

    @staticmethod
    def get_computation_by_filing(db: Session, filing_id: int) -> TaxComputation:
        """Get tax computation for a filing"""
        comp = db.query(TaxComputation).filter(TaxComputation.itr_filing_id == filing_id).first()
        if not comp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax computation not found")
        return comp
