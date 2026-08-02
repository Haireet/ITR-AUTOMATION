"""
Balance Sheet service - business logic for balance sheet operations
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status
from typing import List, Optional

from models import (
    BalanceSheet, BalanceSheetItem, BalanceSheetType, BalanceSheetItemType,
    Transaction, BankStatement, TransactionCategory
)
from schemas.balance_sheet_schemas import (
    BalanceSheetCreate, BalanceSheetUpdate,
    BalanceSheetItemCreate, BalanceSheetItemUpdate,
    BalanceSheetSummary
)


class BalanceSheetService:
    """Service class for balance sheet operations"""

    @staticmethod
    def create_balance_sheet(db: Session, user_id: int, data: BalanceSheetCreate) -> BalanceSheet:
        """Create a new balance sheet with optional items"""
        bs = BalanceSheet(
            user_id=user_id,
            sheet_type=data.sheet_type,
            financial_year=data.financial_year,
            name=data.name,
            notes=data.notes,
        )
        db.add(bs)
        db.flush()

        for item_data in (data.items or []):
            item = BalanceSheetItem(
                balance_sheet_id=bs.id,
                item_type=item_data.item_type,
                category=item_data.category,
                subcategory=item_data.subcategory,
                description=item_data.description,
                amount=item_data.amount,
                as_on_date=item_data.as_on_date,
            )
            db.add(item)

        BalanceSheetService._recalculate_totals(db, bs)
        db.commit()
        db.refresh(bs)
        return bs

    @staticmethod
    def get_balance_sheets(db: Session, user_id: int, sheet_type: Optional[str] = None,
                           financial_year: Optional[str] = None) -> List[BalanceSheet]:
        """List balance sheets for a user with optional filters"""
        query = db.query(BalanceSheet).filter(BalanceSheet.user_id == user_id)
        if sheet_type:
            query = query.filter(BalanceSheet.sheet_type == sheet_type)
        if financial_year:
            query = query.filter(BalanceSheet.financial_year == financial_year)
        return query.order_by(BalanceSheet.updated_at.desc()).all()

    @staticmethod
    def get_balance_sheet(db: Session, bs_id: int, user_id: int) -> BalanceSheet:
        """Get single balance sheet by ID"""
        bs = db.query(BalanceSheet).filter(
            BalanceSheet.id == bs_id,
            BalanceSheet.user_id == user_id
        ).first()
        if not bs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Balance sheet not found")
        return bs

    @staticmethod
    def update_balance_sheet(db: Session, bs_id: int, user_id: int, data: BalanceSheetUpdate) -> BalanceSheet:
        """Update balance sheet metadata"""
        bs = BalanceSheetService.get_balance_sheet(db, bs_id, user_id)
        if data.name is not None:
            bs.name = data.name
        if data.notes is not None:
            bs.notes = data.notes
        db.commit()
        db.refresh(bs)
        return bs

    @staticmethod
    def delete_balance_sheet(db: Session, bs_id: int, user_id: int) -> bool:
        """Delete a balance sheet and all its items"""
        bs = BalanceSheetService.get_balance_sheet(db, bs_id, user_id)
        db.delete(bs)
        db.commit()
        return True

    # ---- Item CRUD ----

    @staticmethod
    def add_item(db: Session, bs_id: int, user_id: int, data: BalanceSheetItemCreate) -> BalanceSheetItem:
        """Add an item to a balance sheet"""
        bs = BalanceSheetService.get_balance_sheet(db, bs_id, user_id)
        item = BalanceSheetItem(
            balance_sheet_id=bs.id,
            item_type=data.item_type,
            category=data.category,
            subcategory=data.subcategory,
            description=data.description,
            amount=data.amount,
            as_on_date=data.as_on_date,
        )
        db.add(item)
        BalanceSheetService._recalculate_totals(db, bs)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def update_item(db: Session, item_id: int, user_id: int, data: BalanceSheetItemUpdate) -> BalanceSheetItem:
        """Update a balance sheet item"""
        item = db.query(BalanceSheetItem).join(BalanceSheet).filter(
            BalanceSheetItem.id == item_id,
            BalanceSheet.user_id == user_id
        ).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        for field in ['item_type', 'category', 'subcategory', 'description', 'amount', 'as_on_date']:
            val = getattr(data, field, None)
            if val is not None:
                setattr(item, field, val)
        BalanceSheetService._recalculate_totals(db, item.balance_sheet)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def delete_item(db: Session, item_id: int, user_id: int) -> bool:
        """Delete a balance sheet item"""
        item = db.query(BalanceSheetItem).join(BalanceSheet).filter(
            BalanceSheetItem.id == item_id,
            BalanceSheet.user_id == user_id
        ).first()
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
        bs = item.balance_sheet
        db.delete(item)
        BalanceSheetService._recalculate_totals(db, bs)
        db.commit()
        return True

    # ---- Auto-generation from transactions ----

    @staticmethod
    def generate_summary_from_transactions(db: Session, user_id: int,
                                           financial_year: str) -> BalanceSheetSummary:
        """
        Auto-generate a personal balance sheet summary from user transactions.
        Groups credits as income and debits as expenses by category.
        """
        txns = (
            db.query(Transaction)
            .join(BankStatement)
            .filter(
                BankStatement.user_id == user_id,
                Transaction.financial_year == financial_year
            )
            .all()
        )

        income_breakdown: dict = {}
        expense_breakdown: dict = {}
        total_income = 0.0
        total_expenses = 0.0

        for t in txns:
            cat = t.category.value if t.category else "uncategorized"
            if t.credit and t.credit > 0:
                income_breakdown[cat] = income_breakdown.get(cat, 0.0) + t.credit
                total_income += t.credit
            if t.debit and t.debit > 0:
                expense_breakdown[cat] = expense_breakdown.get(cat, 0.0) + t.debit
                total_expenses += t.debit

        return BalanceSheetSummary(
            financial_year=financial_year,
            total_income=round(total_income, 2),
            total_expenses=round(total_expenses, 2),
            income_breakdown={k: round(v, 2) for k, v in income_breakdown.items()},
            expense_breakdown={k: round(v, 2) for k, v in expense_breakdown.items()},
            net_worth=round(total_income - total_expenses, 2),
        )

    # ---- Helpers ----

    @staticmethod
    def _recalculate_totals(db: Session, bs: BalanceSheet):
        """Recalculate balance sheet totals from items"""
        db.flush()
        items = db.query(BalanceSheetItem).filter(BalanceSheetItem.balance_sheet_id == bs.id).all()
        bs.total_assets = round(sum(i.amount for i in items if i.item_type == BalanceSheetItemType.ASSET.value or i.item_type == BalanceSheetItemType.ASSET), 2)
        bs.total_liabilities = round(sum(i.amount for i in items if i.item_type == BalanceSheetItemType.LIABILITY.value or i.item_type == BalanceSheetItemType.LIABILITY), 2)
        bs.total_equity = round(sum(i.amount for i in items if i.item_type == BalanceSheetItemType.EQUITY.value or i.item_type == BalanceSheetItemType.EQUITY), 2)
