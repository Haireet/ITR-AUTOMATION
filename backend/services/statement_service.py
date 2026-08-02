"""
Bank statement service - business logic for statement operations
"""
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, UploadFile

from models import BankStatement, Transaction, User, AuditLog, TransactionCategory
from config import settings
from utils.parsers.parser_factory import ParserFactory
from services.classification_service import TransactionClassifier

# Allowed file types
ALLOWED_EXTENSIONS = {'.csv', '.xls', '.xlsx', '.pdf'}
ALLOWED_MIME_TYPES = {
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/pdf'
}

# Maximum file size (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB in bytes

# Upload directory
UPLOAD_DIR = "uploads/bank_statements"


class StatementService:
    """Service class for bank statement operations"""
    
    @staticmethod
    def validate_file(file: UploadFile) -> tuple[bool, Optional[str]]:
        """
        Validate uploaded file type and extension
        
        Args:
            file: Uploaded file object
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if filename exists
        if not file.filename:
            return False, "Filename is required"
        
        # Get file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # Validate extension
        if file_extension not in ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        
        # Validate MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            return False, f"Invalid file MIME type: {file.content_type}"
        
        return True, None
    
    @staticmethod
    async def validate_file_size(file: UploadFile) -> tuple[bool, Optional[str], int]:
        """
        Validate file size
        
        Args:
            file: Uploaded file object
        
        Returns:
            Tuple of (is_valid, error_message, file_size)
        """
        # Read file content to get size
        content = await file.read()
        file_size = len(content)
        
        # Reset file pointer to beginning
        await file.seek(0)
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large. Maximum size: {max_size_mb} MB", file_size
        
        if file_size == 0:
            return False, "File is empty", file_size
        
        return True, None, file_size
    
    @staticmethod
    async def save_file(file: UploadFile, user_id: int) -> str:
        """
        Save uploaded file to disk
        
        Args:
            file: Uploaded file object
            user_id: User ID for organizing files
        
        Returns:
            File path where file was saved
        """
        # Create upload directory if it doesn't exist
        user_upload_dir = os.path.join(UPLOAD_DIR, str(user_id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        original_filename = file.filename
        safe_filename = f"{timestamp}_{original_filename}"
        file_path = os.path.join(user_upload_dir, safe_filename)
        
        # Save file
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        return file_path
    
    @staticmethod
    async def upload_statement(
        db: Session,
        file: UploadFile,
        user: User,
        ip_address: Optional[str] = None
    ) -> BankStatement:
        """
        Handle bank statement upload
        
        Args:
            db: Database session
            file: Uploaded file object
            user: Authenticated user
            ip_address: User's IP address for audit log
        
        Returns:
            Created bank statement record
        
        Raises:
            HTTPException: If validation fails
        """
        # Validate file type
        is_valid, error_message = StatementService.validate_file(file)
        if not is_valid:
            StatementService._create_audit_log(
                db=db,
                user_id=user.id,
                action="statement_upload_failed",
                action_type="file_operation",
                description=f"Failed to upload statement: {error_message}",
                ip_address=ip_address,
                status="failed",
                error_message=error_message
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Validate file size
        is_valid, error_message, file_size = await StatementService.validate_file_size(file)
        if not is_valid:
            StatementService._create_audit_log(
                db=db,
                user_id=user.id,
                action="statement_upload_failed",
                action_type="file_operation",
                description=f"Failed to upload statement: {error_message}",
                ip_address=ip_address,
                status="failed",
                error_message=error_message
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        try:
            # Save file to disk
            file_path = await StatementService.save_file(file, user.id)
            
            # Create database record
            statement = BankStatement(
                user_id=user.id,
                filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                file_type=file.content_type,
                is_processed=False,
                processing_status="pending",
                upload_date=datetime.utcnow()
            )
            
            db.add(statement)
            db.commit()
            db.refresh(statement)
            
            # Create audit log
            StatementService._create_audit_log(
                db=db,
                user_id=user.id,
                action="statement_uploaded",
                action_type="file_operation",
                description=f"Bank statement uploaded: {file.filename}",
                ip_address=ip_address,
                entity_type="bank_statement",
                entity_id=statement.id,
                status="success"
            )
            
            return statement
            
        except Exception as e:
            db.rollback()
            
            # Try to delete file if it was saved
            try:
                if 'file_path' in locals() and os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
            
            StatementService._create_audit_log(
                db=db,
                user_id=user.id,
                action="statement_upload_failed",
                action_type="file_operation",
                description=f"Failed to upload statement: {str(e)}",
                ip_address=ip_address,
                status="failed",
                error_message=str(e)
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload statement: {str(e)}"
            )
    
    @staticmethod
    def get_user_statements(
        db: Session,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[BankStatement]:
        """
        Get all bank statements for a user
        
        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
        
        Returns:
            List of bank statements
        """
        return db.query(BankStatement)\
            .filter(BankStatement.user_id == user_id)\
            .order_by(BankStatement.upload_date.desc())\
            .offset(skip)\
            .limit(limit)\
            .all()
    
    @staticmethod
    def get_statement_by_id(db: Session, statement_id: int, user_id: int) -> BankStatement:
        """
        Get specific bank statement by ID
        
        Args:
            db: Database session
            statement_id: Statement ID
            user_id: User ID (for authorization)
        
        Returns:
            Bank statement
        
        Raises:
            HTTPException: If statement not found or unauthorized
        """
        statement = db.query(BankStatement)\
            .filter(BankStatement.id == statement_id)\
            .first()
        
        if not statement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bank statement not found"
            )
        
        # Check if user owns this statement
        if statement.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this statement"
            )
        
        return statement
    
    @staticmethod
    def process_statement(
        db: Session,
        statement_id: int,
        user_id: int,
        ip_address: Optional[str] = None,
        pdf_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a bank statement - parse file and extract transactions
        
        Args:
            db: Database session
            statement_id: Statement ID
            user_id: User ID (for authorization)
            ip_address: User's IP address for audit log
            pdf_password: Optional password for encrypted PDF files
        
        Returns:
            Dict with processing results
        
        Raises:
            HTTPException: If statement not found, unauthorized, or processing fails
        """
        statement = StatementService.get_statement_by_id(db, statement_id, user_id)
        
        # Update status to processing
        statement.processing_status = "processing"
        statement.error_message = None
        db.commit()
        
        try:
            # Parse the file
            result = ParserFactory.parse_statement(
                file_path=statement.file_path,
                file_type=statement.file_type,
                password=pdf_password
            )
            
            # Check for password-required error
            if not result.success and result.error_message == "PDF_PASSWORD_REQUIRED":
                statement.processing_status = "password_required"
                statement.error_message = "This PDF is password protected. Please provide the password."
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="PDF_PASSWORD_REQUIRED"
                )
            
            if not result.success:
                statement.processing_status = "failed"
                statement.error_message = result.error_message
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=result.error_message or "Failed to parse statement"
                )
            
            # Delete existing transactions for re-processing
            db.query(Transaction).filter(
                Transaction.statement_id == statement_id
            ).delete()
            
            # Create transactions from parsed data
            classifier = TransactionClassifier()
            for parsed_txn in result.transactions:
                category, confidence = classifier.classify(
                    parsed_txn.description,
                    is_credit=(parsed_txn.credit > 0)
                )
                
                txn = Transaction(
                    statement_id=statement_id,
                    date=parsed_txn.date,
                    description=parsed_txn.description,
                    debit=parsed_txn.debit,
                    credit=parsed_txn.credit,
                    balance=parsed_txn.balance,
                    category=category,
                    confidence_score=confidence,
                    manually_labeled=False,
                    is_tax_relevant=(category.value != "uncategorized"),
                )
                db.add(txn)
            
            # Update statement metadata
            statement.is_processed = True
            statement.processing_status = "completed"
            statement.processed_date = datetime.utcnow()
            statement.error_message = None
            
            if result.metadata:
                if result.metadata.bank_name:
                    statement.bank_name = result.metadata.bank_name
                if result.metadata.account_number:
                    statement.account_number = result.metadata.account_number
                if result.metadata.statement_period_start:
                    statement.statement_period_start = result.metadata.statement_period_start
                if result.metadata.statement_period_end:
                    statement.statement_period_end = result.metadata.statement_period_end
            
            db.commit()
            
            # Audit log
            StatementService._create_audit_log(
                db=db,
                user_id=user_id,
                action="statement_processed",
                action_type="file_operation",
                description=f"Statement processed: {len(result.transactions)} transactions extracted",
                ip_address=ip_address,
                entity_type="bank_statement",
                entity_id=statement_id,
                status="success"
            )
            
            return {
                "statement_id": statement_id,
                "transactions_extracted": len(result.transactions),
                "bank_name": statement.bank_name,
                "account_number": statement.account_number,
                "statement_period_start": statement.statement_period_start,
                "statement_period_end": statement.statement_period_end,
                "warnings": result.warnings or [],
                "processing_status": "completed"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            statement.processing_status = "failed"
            statement.error_message = str(e)
            db.commit()
            
            StatementService._create_audit_log(
                db=db,
                user_id=user_id,
                action="statement_processing_failed",
                action_type="file_operation",
                description=f"Processing failed: {str(e)}",
                ip_address=ip_address,
                entity_type="bank_statement",
                entity_id=statement_id,
                status="failed",
                error_message=str(e)
            )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process statement: {str(e)}"
            )
    
    @staticmethod
    def delete_statement(
        db: Session,
        statement_id: int,
        user_id: int,
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Delete bank statement and associated file
        
        Args:
            db: Database session
            statement_id: Statement ID
            user_id: User ID (for authorization)
            ip_address: User's IP address for audit log
        
        Returns:
            True if successful
        
        Raises:
            HTTPException: If statement not found or unauthorized
        """
        # Get statement
        statement = StatementService.get_statement_by_id(db, statement_id, user_id)
        
        try:
            # Delete file from disk
            if statement.file_path and os.path.exists(statement.file_path):
                os.remove(statement.file_path)
            
            # Delete database record (cascades to transactions)
            db.delete(statement)
            db.commit()
            
            # Create audit log
            StatementService._create_audit_log(
                db=db,
                user_id=user_id,
                action="statement_deleted",
                action_type="file_operation",
                description=f"Bank statement deleted: {statement.filename}",
                ip_address=ip_address,
                entity_type="bank_statement",
                entity_id=statement_id,
                status="success"
            )
            
            return True
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete statement: {str(e)}"
            )
    
    @staticmethod
    def _create_audit_log(
        db: Session,
        user_id: int,
        action: str,
        action_type: str,
        description: str = None,
        ip_address: str = None,
        entity_type: str = None,
        entity_id: int = None,
        status: str = "success",
        error_message: str = None
    ):
        """
        Internal method to create audit log entries
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                action_type=action_type,
                description=description,
                ip_address=ip_address,
                entity_type=entity_type,
                entity_id=entity_id,
                status=status,
                error_message=error_message,
                timestamp=datetime.utcnow()
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to create audit log: {str(e)}")
