"""
CA Review router - handles CA review workflow
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from typing import Optional
import math

from database import get_db
from models import User, UserRole, ITRFiling
from utils.security import get_current_user
from services.review_service import ReviewService
from services.export_service import ExportService
from schemas.review_schemas import (
    TransactionCategoryUpdate,
    TransactionReviewResponse,
    TransactionListResponse,
    ITRReviewComment,
    ITRApproval,
    ITRReviewStatus,
    AuditLogResponse,
    AuditLogListResponse,
    ReviewSummary,
    CADashboard
)
from schemas import MessageResponse, ITRFilingResponse
from schemas.statement_schemas import BankStatementResponse
from fastapi.responses import Response, JSONResponse

router = APIRouter()

def _pdf_response(pdf_data, filename: str) -> Response:
    return Response(
        content=bytes(pdf_data),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

def _normalized_role(user: User) -> str:
    if hasattr(user.role, "value"):
        return str(user.role.value).lower()
    return str(user.role).lower()


@router.get(
    "/filings",
    summary="Get all ITR filings for review",
    description="CA retrieves all users' ITR filings for review"
)
async def get_all_filings_for_review(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by review_status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all ITR filings across all users (CA/Admin only).
    Returns filing data enriched with user_name and user_email.
    """
    if _normalized_role(current_user) not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="CA/Admin access required")

    query = db.query(ITRFiling).order_by(ITRFiling.updated_at.desc())
    if status_filter:
        query = query.filter(ITRFiling.review_status == status_filter)
    filings = query.all()

    result = []
    for f in filings:
        user = db.query(User).filter(User.id == f.user_id).first()
        result.append({
            "id": f.id,
            "user_id": f.user_id,
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "",
            "assessment_year": f.assessment_year,
            "form_type": f.form_type,
            "status": f.status,
            "review_status": f.review_status,
            "filing_date": f.filing_date.isoformat() if f.filing_date else None,
            "acknowledgement_number": f.acknowledgement_number,
            "ca_comments": f.ca_comments,
            "reviewed_by": f.reviewed_by,
            "approved_by": f.approved_by,
            "created_at": f.created_at.isoformat() if f.created_at else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        })
    return result


@router.get(
    "/transactions/{user_id}",
    response_model=TransactionListResponse,
    summary="Get transactions for review",
    description="CA retrieves user's transactions for review with filters"
)
async def get_transactions_for_review(
    user_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    statement_id: Optional[int] = Query(None, description="Filter by statement ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_tax_relevant: Optional[bool] = Query(None, description="Filter by tax relevance"),
    manually_labeled: Optional[bool] = Query(None, description="Filter by manual label status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's transactions for CA review
    
    **Access**: CA, Admin, Auditor only
    
    Args:
        user_id: User whose transactions to review
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        category: Filter by category
        is_tax_relevant: Filter by tax relevance
        manually_labeled: Filter by manual label status
    
    Returns:
        TransactionListResponse: Paginated transaction list
    
    Raises:
        403: Not authorized (user is not CA/Admin/Auditor)
        404: User not found
    """
    skip = (page - 1) * page_size
    
    transactions, total = ReviewService.get_transactions_for_review(
        db=db,
        user_id=user_id,
        ca_user=current_user,
        skip=skip,
        limit=page_size,
        statement_id=statement_id,
        category=category,
        is_tax_relevant=is_tax_relevant,
        manually_labeled=manually_labeled
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return TransactionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        transactions=[TransactionReviewResponse.model_validate(t) for t in transactions]
    )


@router.get(
    "/statements/{user_id}",
    response_model=list[BankStatementResponse],
    summary="Get user statements for review",
    description="CA retrieves user's bank statements for scoped transaction review"
)
async def get_user_statements_for_review(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    statements = ReviewService.get_user_statements_for_review(
        db=db,
        user_id=user_id,
        ca_user=current_user
    )
    return [BankStatementResponse.model_validate(s) for s in statements]


@router.put(
    "/transactions/{transaction_id}/category",
    response_model=TransactionReviewResponse,
    summary="Update transaction category",
    description="CA updates transaction category with audit trail"
)
async def update_transaction_category(
    transaction_id: int,
    category_update: TransactionCategoryUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CA updates transaction category
    
    **Access**: CA, Admin, Auditor only
    
    **Audit Trail**: All changes are logged immutably
    
    Args:
        transaction_id: Transaction ID to update
        category_update: New category and notes
    
    Returns:
        TransactionReviewResponse: Updated transaction
    
    Raises:
        403: Not authorized
        404: Transaction not found
        400: Invalid category
    
    Example:
        ```json
        {
          "category": "salary",
          "notes": "Verified as monthly salary from employer"
        }
        ```
    """
    ip_address = request.client.host if request.client else None
    
    transaction = ReviewService.update_transaction_category(
        db=db,
        transaction_id=transaction_id,
        ca_user=current_user,
        new_category=category_update.category,
        notes=category_update.notes,
        ip_address=ip_address
    )
    
    return TransactionReviewResponse.model_validate(transaction)


@router.get(
    "/itr/{filing_id}",
    response_model=ITRReviewStatus,
    summary="Get ITR for review",
    description="CA retrieves ITR filing for review"
)
async def get_itr_for_review(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get ITR filing for CA review
    
    **Access**: CA, Admin, Auditor only
    
    Args:
        filing_id: ITR filing ID
    
    Returns:
        ITRReviewStatus: ITR filing details
    
    Raises:
        403: Not authorized
        404: ITR filing not found
    """
    filing = ReviewService.get_itr_for_review(
        db=db,
        filing_id=filing_id,
        ca_user=current_user
    )
    
    return ITRReviewStatus.model_validate(filing)


@router.post(
    "/itr/{filing_id}/comment",
    response_model=MessageResponse,
    summary="Add review comment",
    description="CA adds review comment to ITR filing"
)
async def add_review_comment(
    filing_id: int,
    comment_data: ITRReviewComment,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CA adds review comment to ITR filing
    
    **Access**: CA, Admin, Auditor only
    
    **Audit Trail**: Comment is logged immutably
    
    Args:
        filing_id: ITR filing ID
        comment_data: Review comment and type
    
    Returns:
        MessageResponse: Confirmation
    
    Raises:
        403: Not authorized
        404: ITR filing not found
    
    Example:
        ```json
        {
          "comment": "Please verify salary income amount",
          "comment_type": "clarification"
        }
        ```
    """
    ip_address = request.client.host if request.client else None
    
    ReviewService.add_review_comment(
        db=db,
        filing_id=filing_id,
        ca_user=current_user,
        comment=comment_data.comment,
        comment_type=comment_data.comment_type,
        ip_address=ip_address
    )
    
    return MessageResponse(
        message="Review comment added successfully",
        detail=f"Comment type: {comment_data.comment_type}"
    )


@router.post(
    "/itr/{filing_id}/approve",
    response_model=ITRReviewStatus,
    summary="Approve or request changes to ITR",
    description="CA approves ITR or requests changes"
)
async def approve_itr(
    filing_id: int,
    approval_data: ITRApproval,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CA approves or requests changes to ITR filing
    
    **Access**: CA, Admin, Auditor only
    
    **Audit Trail**: Approval decision is logged immutably
    
    Args:
        filing_id: ITR filing ID
        approval_data: Approval status and comments
    
    Returns:
        ITRReviewStatus: Updated ITR filing status
    
    Raises:
        403: Not authorized
        404: ITR filing not found
    
    Example (Approval):
        ```json
        {
          "approved": true,
          "ca_comments": "All documents verified. Ready for filing.",
          "suggestions": ["Consider tax-saving FD for next year"]
        }
        ```
    
    Example (Request Changes):
        ```json
        {
          "approved": false,
          "ca_comments": "Please provide proof for deduction claims",
          "suggestions": [
            "Upload Form 16",
            "Provide 80C investment proof"
          ]
        }
        ```
    """
    ip_address = request.client.host if request.client else None
    
    filing = ReviewService.approve_itr(
        db=db,
        filing_id=filing_id,
        ca_user=current_user,
        approved=approval_data.approved,
        ca_comments=approval_data.ca_comments,
        ip_address=ip_address
    )
    
    return ITRReviewStatus.model_validate(filing)


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Get audit logs",
    description="CA retrieves audit logs (read-only)"
)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get audit logs for review
    
    **Access**: CA, Admin, Auditor only
    
    **Read-Only**: Audit logs are immutable and cannot be modified
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page (max 100)
        user_id: Filter by user ID
        entity_type: Filter by entity type (e.g., 'transaction', 'itr_filing')
        entity_id: Filter by entity ID
        action_type: Filter by action type
    
    Returns:
        AuditLogListResponse: Paginated audit log list
    
    Raises:
        403: Not authorized
    """
    skip = (page - 1) * page_size
    
    logs, total = ReviewService.get_audit_logs(
        db=db,
        ca_user=current_user,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        skip=skip,
        limit=page_size
    )
    
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        logs=[AuditLogResponse.model_validate(log) for log in logs]
    )


@router.get(
    "/summary/{user_id}",
    response_model=ReviewSummary,
    summary="Get review summary",
    description="CA gets review summary statistics for a user"
)
async def get_review_summary(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get review summary statistics for a user
    
    **Access**: CA, Admin, Auditor only
    
    Args:
        user_id: User ID
    
    Returns:
        ReviewSummary: Statistics including:
        - Total transactions
        - Reviewed vs pending
        - Tax-relevant transactions
        - Income and deductions summary
        - Category breakdown
        - Review progress percentage
    
    Raises:
        403: Not authorized
        404: User not found
    """
    summary = ReviewService.get_review_summary(
        db=db,
        user_id=user_id,
        ca_user=current_user
    )
    
    return ReviewSummary(**summary)


@router.get(
    "/dashboard",
    response_model=CADashboard,
    summary="Get CA dashboard",
    description="CA dashboard with overview statistics"
)
async def get_ca_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get CA dashboard statistics
    
    **Access**: CA, Admin, Auditor only
    
    Returns:
        CADashboard: Dashboard data including:
        - Assigned users count
        - Pending reviews count
        - Approved ITRs count
        - Total transactions reviewed
        - Recent activity
    
    Raises:
        403: Not authorized
    """
    dashboard = ReviewService.get_ca_dashboard(
        db=db,
        ca_user=current_user
    )
    
    return CADashboard(**dashboard)


@router.get("/export/itr/{filing_id}/pdf")
async def export_itr_pdf_for_review(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filing = ReviewService.get_itr_for_review(db, filing_id, current_user)
    pdf_bytes = ExportService.export_itr_pdf(db, filing_id, filing.user_id)
    return _pdf_response(pdf_bytes, f"ITR_{filing_id}_CA.pdf")


@router.get("/export/itr/{filing_id}/json")
async def export_itr_json_for_review(
    filing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filing = ReviewService.get_itr_for_review(db, filing_id, current_user)
    data = ExportService.export_itr_json(db, filing_id, filing.user_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=ITR_{filing_id}_CA.json"},
    )


@router.get("/export/transactions/{statement_id}/pdf")
async def export_transactions_pdf_for_review(
    statement_id: int,
    user_id: int = Query(..., description="Owner user ID of the statement"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ReviewService.verify_ca_access(db, current_user, user_id)
    pdf_bytes = ExportService.export_transactions_pdf(db, statement_id, user_id)
    return _pdf_response(pdf_bytes, f"Transactions_{statement_id}_CA.pdf")


@router.get("/export/transactions/{statement_id}/json")
async def export_transactions_json_for_review(
    statement_id: int,
    user_id: int = Query(..., description="Owner user ID of the statement"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ReviewService.verify_ca_access(db, current_user, user_id)
    data = ExportService.export_transactions_json(db, statement_id, user_id)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=Transactions_{statement_id}_CA.json"},
    )
