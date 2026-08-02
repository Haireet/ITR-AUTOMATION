"""
Bank statement router - handles statement upload and management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import User, BankStatement, Transaction, TransactionCategory
from utils.security import get_current_user
from services.statement_service import StatementService
from schemas.statement_schemas import (
    BankStatementResponse,
    BankStatementUploadResponse,
    BankStatementListResponse,
    ProcessStatementResponse,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest
)
from schemas import MessageResponse

router = APIRouter()


@router.post(
    "/{statement_id}/process",
    response_model=ProcessStatementResponse,
    summary="Process bank statement",
    description="Parse a bank statement and extract transactions. Supports optional PDF password."
)
async def process_statement(
    statement_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a bank statement file - parse and extract transactions.
    Send {"pdf_password": "..."} in body for encrypted PDFs.
    """
    ip_address = request.client.host if request.client else None
    
    # Read pdf_password from JSON body (no FastAPI Body validation)
    pdf_password = None
    try:
        body = await request.json()
        if isinstance(body, dict):
            pdf_password = body.get("pdf_password")
    except Exception:
        pass
    
    result = StatementService.process_statement(
        db=db,
        statement_id=statement_id,
        user_id=current_user.id,
        ip_address=ip_address,
        pdf_password=pdf_password
    )
    
    return ProcessStatementResponse(
        message="Statement processed successfully",
        **result
    )


@router.post(
    "/upload",
    response_model=BankStatementUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload bank statement",
    description="Upload a bank statement file (CSV, XLS, XLSX, or PDF)"
)
async def upload_bank_statement(
    request: Request,
    file: UploadFile = File(..., description="Bank statement file to upload"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a bank statement file
    
    - **file**: Bank statement file (CSV, XLS, XLSX, PDF)
    - Maximum file size: 10 MB
    - File will be saved and associated with the authenticated user
    - Parsing and transaction extraction happens in a separate step
    
    Returns:
        BankStatementUploadResponse: Upload confirmation with statement metadata
    
    Raises:
        400: Invalid file type or size
        401: Unauthorized (no valid token)
        500: Server error during upload
    
    Example:
        ```bash
        curl -X POST "http://localhost:8000/api/statements/upload" \\
          -H "Authorization: Bearer <token>" \\
          -F "file=@statement.csv"
        ```
    """
    # Get client IP address
    ip_address = request.client.host if request.client else None
    
    # Upload statement
    statement = await StatementService.upload_statement(
        db=db,
        file=file,
        user=current_user,
        ip_address=ip_address
    )
    
    return BankStatementUploadResponse(
        message="Bank statement uploaded successfully",
        statement=BankStatementResponse.model_validate(statement),
        detail=f"File saved: {file.filename}. Processing status: {statement.processing_status}"
    )


@router.get(
    "",
    response_model=BankStatementListResponse,
    summary="Get user's bank statements",
    description="Retrieve all bank statements uploaded by the authenticated user"
)
async def get_user_statements(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all bank statements for the authenticated user
    
    Supports pagination with skip and limit parameters.
    
    Returns:
        BankStatementListResponse: List of bank statements with total count
    
    Raises:
        401: Unauthorized (no valid token)
    """
    statements = StatementService.get_user_statements(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    
    # Get total count
    total = db.query(BankStatement).filter(
    BankStatement.user_id == current_user.id
).count()
    
    return BankStatementListResponse(
        total=total,
        statements=[BankStatementResponse.model_validate(s) for s in statements]
    )


@router.get(
    "/{statement_id}",
    response_model=BankStatementResponse,
    summary="Get specific bank statement",
    description="Retrieve a specific bank statement by ID"
)
async def get_statement(
    statement_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific bank statement by ID
    
    User can only access their own statements.
    
    Args:
        statement_id: Bank statement ID
    
    Returns:
        BankStatementResponse: Bank statement details
    
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (statement belongs to another user)
        404: Statement not found
    """
    statement = StatementService.get_statement_by_id(
        db=db,
        statement_id=statement_id,
        user_id=current_user.id
    )
    
    return BankStatementResponse.model_validate(statement)


@router.get(
    "/{statement_id}/transactions",
    response_model=TransactionListResponse,
    summary="Get transactions for a statement",
    description="Retrieve all transactions extracted from a specific bank statement"
)
async def get_statement_transactions(
    statement_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify ownership
    statement = StatementService.get_statement_by_id(db, statement_id, current_user.id)

    total = db.query(Transaction).filter(Transaction.statement_id == statement_id).count()
    transactions = (
        db.query(Transaction)
        .filter(Transaction.statement_id == statement_id)
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return TransactionListResponse(
        total=total,
        statement_id=statement_id,
        transactions=[TransactionResponse.model_validate(t) for t in transactions]
    )


@router.patch(
    "/transactions/{transaction_id}/category",
    response_model=TransactionResponse,
    summary="Update transaction category",
    description="Update the category and optional notes for a transaction"
)
async def update_transaction_category(
    transaction_id: int,
    update: TransactionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Verify ownership via statement
    statement = db.query(BankStatement).filter(
        BankStatement.id == txn.statement_id,
        BankStatement.user_id == current_user.id
    ).first()
    if not statement:
        raise HTTPException(status_code=403, detail="Not authorized")

    try:
        txn.category = TransactionCategory(update.category)
    except ValueError:
        txn.category = TransactionCategory.UNCATEGORIZED

    txn.manually_labeled = True
    if update.notes is not None:
        txn.notes = update.notes
    db.commit()
    db.refresh(txn)

    return TransactionResponse.model_validate(txn)


@router.delete(
    "/{statement_id}",
    response_model=MessageResponse,
    summary="Delete bank statement",
    description="Delete a bank statement and its associated file"
)
async def delete_statement(
    statement_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a bank statement and its file
    
    This will also delete all associated transactions (cascade delete).
    User can only delete their own statements.
    
    Args:
        statement_id: Bank statement ID
    
    Returns:
        MessageResponse: Deletion confirmation
    
    Raises:
        401: Unauthorized (no valid token)
        403: Forbidden (statement belongs to another user)
        404: Statement not found
        500: Server error during deletion
    """
    # Get client IP address
    ip_address = request.client.host if request.client else None
    
    # Delete statement
    StatementService.delete_statement(
        db=db,
        statement_id=statement_id,
        user_id=current_user.id,
        ip_address=ip_address
    )
    
    return MessageResponse(
        message="Bank statement deleted successfully",
        detail=f"Statement ID {statement_id} and associated file have been removed"
    )
