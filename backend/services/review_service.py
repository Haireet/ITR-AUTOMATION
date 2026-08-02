"""
Review service - CA review workflow business logic
"""
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from fastapi import HTTPException, status

from models import (
    User, Transaction, ITRFiling, AuditLog, BankStatement,
    UserRole, TransactionCategory
)


class ReviewService:
    """Service class for CA review operations"""

    @staticmethod
    def _is_reviewer(user: User) -> bool:
        role = str(getattr(user, "role", "")).lower()
        if hasattr(user.role, "value"):
            role = str(user.role.value).lower()
        return role in ("admin", "auditor")
    
    @staticmethod
    def verify_ca_access(db: Session, ca_user: User, target_user_id: int) -> bool:
        """
        Verify CA has access to review user's data
        
        Args:
            db: Database session
            ca_user: CA user object
            target_user_id: Target user ID to review
        
        Returns:
            True if CA has access
        
        Raises:
            HTTPException: If access denied
        """
        # Admin and Auditor roles can access all users
        if ReviewService._is_reviewer(ca_user):
            return True
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to review this user's data"
        )
    
    @staticmethod
    def get_transactions_for_review(
        db: Session,
        user_id: int,
        ca_user: User,
        skip: int = 0,
        limit: int = 100,
        statement_id: Optional[int] = None,
        category: Optional[str] = None,
        is_tax_relevant: Optional[bool] = None,
        manually_labeled: Optional[bool] = None
    ) -> tuple:
        """
        Get transactions for CA review with filters
        
        Args:
            db: Database session
            user_id: User whose transactions to review
            ca_user: CA user performing review
            skip: Pagination skip
            limit: Pagination limit
            category: Filter by category
            is_tax_relevant: Filter by tax relevance
            manually_labeled: Filter by manual label status
        
        Returns:
            Tuple of (transactions list, total count)
        """
        # Verify CA access
        ReviewService.verify_ca_access(db, ca_user, user_id)
        
        # Build query
        query = db.query(Transaction).join(
            Transaction.statement
        ).filter(
            Transaction.statement.has(user_id=user_id)
        )
        
        # Apply filters
        if statement_id is not None:
            query = query.filter(Transaction.statement_id == statement_id)

        if category:
            query = query.filter(Transaction.category == category)
        
        if is_tax_relevant is not None:
            query = query.filter(Transaction.is_tax_relevant == is_tax_relevant)
        
        if manually_labeled is not None:
            query = query.filter(Transaction.manually_labeled == manually_labeled)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        transactions = query.order_by(
            Transaction.date.desc()
        ).offset(skip).limit(limit).all()
        
        return transactions, total

    @staticmethod
    def get_user_statements_for_review(
        db: Session,
        user_id: int,
        ca_user: User
    ) -> List[BankStatement]:
        """Get target user's statements for CA review"""
        ReviewService.verify_ca_access(db, ca_user, user_id)
        return db.query(BankStatement).filter(
            BankStatement.user_id == user_id
        ).order_by(BankStatement.upload_date.desc()).all()
    
    @staticmethod
    def update_transaction_category(
        db: Session,
        transaction_id: int,
        ca_user: User,
        new_category: str,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Transaction:
        """
        CA updates transaction category (immutable audit trail)
        
        Args:
            db: Database session
            transaction_id: Transaction ID
            ca_user: CA user performing update
            new_category: New category value
            notes: CA's review notes
            ip_address: CA's IP address
        
        Returns:
            Updated transaction
        
        Raises:
            HTTPException: If transaction not found or access denied
        """
        # Get transaction
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found"
            )
        
        # Get user_id from transaction's statement
        user_id = transaction.statement.user_id
        
        # Verify CA access
        ReviewService.verify_ca_access(db, ca_user, user_id)
        
        # Validate category
        try:
            TransactionCategory(new_category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {new_category}"
            )
        
        # Store old values for audit
        old_category = transaction.category
        old_manually_labeled = transaction.manually_labeled
        
        # Update transaction
        transaction.category = new_category
        transaction.manually_labeled = True
        transaction.notes = notes
        transaction.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(transaction)
        
        # Create immutable audit log
        ReviewService._create_audit_log(
            db=db,
            user_id=ca_user.id,
            action="ca_category_update",
            action_type="data_modification",
            description=(
                f"CA updated transaction category: "
                f"{old_category} → {new_category} "
                f"(Transaction ID: {transaction_id}, User ID: {user_id})"
            ),
            ip_address=ip_address,
            entity_type="transaction",
            entity_id=transaction_id,
            status="success",
            extra_data=(
                f"old_category={old_category}|"
                f"new_category={new_category}|"
                f"old_manually_labeled={old_manually_labeled}|"
                f"notes={notes or 'None'}"
            )
        )
        
        return transaction
    
    @staticmethod
    def get_itr_for_review(
        db: Session,
        filing_id: int,
        ca_user: User
    ) -> ITRFiling:
        """
        Get ITR filing for CA review
        
        Args:
            db: Database session
            filing_id: ITR filing ID
            ca_user: CA user performing review
        
        Returns:
            ITR filing
        
        Raises:
            HTTPException: If filing not found or access denied
        """
        filing = db.query(ITRFiling).filter(
            ITRFiling.id == filing_id
        ).first()
        
        if not filing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITR filing not found"
            )
        
        # Verify CA access
        ReviewService.verify_ca_access(db, ca_user, filing.user_id)
        
        return filing
    
    @staticmethod
    def add_review_comment(
        db: Session,
        filing_id: int,
        ca_user: User,
        comment: str,
        comment_type: str = "general",
        ip_address: Optional[str] = None
    ) -> bool:
        """
        CA adds review comment to ITR filing
        
        Args:
            db: Database session
            filing_id: ITR filing ID
            ca_user: CA user
            comment: Review comment
            comment_type: Type of comment
            ip_address: CA's IP address
        
        Returns:
            True if successful
        """
        # Verify filing exists and CA has access
        filing = ReviewService.get_itr_for_review(db, filing_id, ca_user)

        # Move filing into active review workflow if still pending
        if filing.review_status in ("pending_review", "pending_ca_approval"):
            filing.review_status = "under_review"
            filing.reviewed_by = ca_user.id
            filing.reviewed_at = datetime.utcnow()
            filing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(filing)
        
        # Create immutable audit log for comment
        ReviewService._create_audit_log(
            db=db,
            user_id=ca_user.id,
            action="ca_review_comment",
            action_type="data_access",
            description=(
                f"CA added review comment: {comment_type} "
                f"(Filing ID: {filing_id}, User ID: {filing.user_id})"
            ),
            ip_address=ip_address,
            entity_type="itr_filing",
            entity_id=filing_id,
            status="success",
            extra_data=f"comment_type={comment_type}|comment={comment}"
        )
        
        return True
    
    @staticmethod
    def approve_itr(
        db: Session,
        filing_id: int,
        ca_user: User,
        approved: bool,
        ca_comments: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> ITRFiling:
        """
        CA approves or requests changes to ITR filing
        
        Args:
            db: Database session
            filing_id: ITR filing ID
            ca_user: CA user
            approved: Approval status
            ca_comments: CA's final comments
            ip_address: CA's IP address
        
        Returns:
            Updated ITR filing
        
        Raises:
            HTTPException: If filing not found or access denied
        """
        # Verify filing exists and CA has access
        filing = ReviewService.get_itr_for_review(db, filing_id, ca_user)
        
        # Store old status
        old_status = filing.review_status
        
        # Update review status and CA fields
        if approved:
            filing.review_status = "approved"
            filing.approved_by = ca_user.id
            filing.approved_at = datetime.utcnow()
        else:
            filing.review_status = "changes_requested"
        
        filing.reviewed_by = ca_user.id
        filing.reviewed_at = datetime.utcnow()
        if ca_comments:
            filing.ca_comments = ca_comments
        filing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(filing)
        
        # Create immutable audit log
        ReviewService._create_audit_log(
            db=db,
            user_id=ca_user.id,
            action="ca_itr_approval" if approved else "ca_itr_rejection",
            action_type="data_modification",
            description=(
                f"CA {'approved' if approved else 'requested changes to'} ITR filing "
                f"(Filing ID: {filing_id}, User ID: {filing.user_id})"
            ),
            ip_address=ip_address,
            entity_type="itr_filing",
            entity_id=filing_id,
            status="success",
            extra_data=(
                f"old_status={old_status}|"
                f"new_status={filing.review_status}|"
                f"approved={approved}|"
                f"ca_comments={ca_comments or 'None'}"
            )
        )
        
        return filing
    
    @staticmethod
    def get_audit_logs(
        db: Session,
        ca_user: User,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        action_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple:
        """
        Get audit logs for review (read-only, immutable)
        
        Args:
            db: Database session
            ca_user: CA user requesting logs
            user_id: Filter by user ID
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            action_type: Filter by action type
            skip: Pagination skip
            limit: Pagination limit
        
        Returns:
            Tuple of (audit logs list, total count)
        """
        # Only CA/Admin/Auditor can view audit logs
        if not ReviewService._is_reviewer(ca_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view audit logs"
            )
        
        # Build query
        query = db.query(AuditLog)
        
        # Apply filters
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)
        
        if action_type:
            query = query.filter(AuditLog.action_type == action_type)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        logs = query.order_by(
            AuditLog.timestamp.desc()
        ).offset(skip).limit(limit).all()
        
        return logs, total
    
    @staticmethod
    def get_review_summary(
        db: Session,
        user_id: int,
        ca_user: User
    ) -> Dict:
        """
        Get review summary statistics for a user
        
        Args:
            db: Database session
            user_id: User ID
            ca_user: CA user
        
        Returns:
            Dictionary with review statistics
        """
        # Verify CA access
        ReviewService.verify_ca_access(db, ca_user, user_id)
        
        # Get all transactions for user
        transactions = db.query(Transaction).join(
            Transaction.statement
        ).filter(
            Transaction.statement.has(user_id=user_id)
        ).all()
        
        total_transactions = len(transactions)
        reviewed_transactions = sum(1 for t in transactions if t.manually_labeled)
        tax_relevant = sum(1 for t in transactions if t.is_tax_relevant)
        
        # Calculate income and deductions
        total_income = sum(t.credit for t in transactions if t.is_tax_relevant and t.credit > 0)
        total_deductions = sum(t.debit for t in transactions if t.is_tax_relevant and t.debit > 0)
        
        # Category breakdown
        category_counts = {}
        for t in transactions:
            category = t.category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            'total_transactions': total_transactions,
            'reviewed_transactions': reviewed_transactions,
            'pending_review': total_transactions - reviewed_transactions,
            'tax_relevant_transactions': tax_relevant,
            'total_income': round(total_income, 2),
            'total_deductions': round(total_deductions, 2),
            'categories_breakdown': category_counts,
            'review_progress_percentage': round(
                (reviewed_transactions / total_transactions * 100) if total_transactions > 0 else 0,
                2
            )
        }
    
    @staticmethod
    def get_ca_dashboard(
        db: Session,
        ca_user: User
    ) -> Dict:
        """
        Get CA dashboard statistics
        
        Args:
            db: Database session
            ca_user: CA user
        
        Returns:
            Dictionary with dashboard data
        """
        # Only CA/Admin/Auditor can access dashboard
        if not ReviewService._is_reviewer(ca_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access CA dashboard"
            )
        
        # Count pending reviews (ITR filings in draft/completed status)
        pending_reviews = db.query(ITRFiling).filter(
            ITRFiling.review_status.in_(['pending_review', 'pending_ca_approval', 'under_review', 'changes_requested'])
        ).count()
        
        # Count approved ITRs
        approved_itrs = db.query(ITRFiling).filter(
            ITRFiling.review_status == 'approved'
        ).count()
        
        # Count total users
        assigned_users = db.query(User).filter(
            User.role == UserRole.USER
        ).count()
        
        # Count transactions reviewed by this CA
        total_reviewed = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == ca_user.id,
                AuditLog.action == 'ca_category_update'
            )
        ).count()
        
        # Get recent activity (last 10 actions)
        recent_activity = db.query(AuditLog).filter(
            AuditLog.user_id == ca_user.id
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(10).all()
        
        recent_activity_list = [
            {
                'action': log.action,
                'description': log.description,
                'timestamp': log.timestamp.isoformat(),
                'entity_type': log.entity_type,
                'entity_id': log.entity_id
            }
            for log in recent_activity
        ]
        
        return {
            'assigned_users': assigned_users,
            'pending_reviews': pending_reviews,
            'approved_itrs': approved_itrs,
            'total_transactions_reviewed': total_reviewed,
            'recent_activity': recent_activity_list
        }
    
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
        error_message: str = None,
        extra_data: str = None
    ):
        """
        Create immutable audit log entry
        
        Note: Audit logs are INSERT-ONLY, never UPDATE or DELETE
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
                extra_data=extra_data,
                timestamp=datetime.utcnow()
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to create audit log: {str(e)}")
