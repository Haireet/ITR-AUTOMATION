"""
Consolidation Service — merge bank statements & calculate ITR

Handles:
1. Merging transactions from multiple bank statements (deduplication)
2. Categorized income/deduction summary
3. Indian income tax calculation (Old & New regime, AY 2025-26)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Tuple
from datetime import datetime
import json

from models import BankStatement, Transaction, ITRFiling, TaxComputation, TransactionCategory


# ──────────────────────────────────────────────────
#  CATEGORY → INCOME / DEDUCTION MAPPING
# ──────────────────────────────────────────────────
INCOME_CATEGORIES = {
    "salary": "salary_income",
    "interest": "interest_income",
    "dividend": "dividend_income",
    "rental_income": "rental_income",
    "capital_gains": "capital_gains",
    "business_income": "business_income",
}

DEDUCTION_CATEGORIES = {
    "deduction_80c": "deduction_80c",
    "deduction_80d": "deduction_80d",
    "home_loan_interest": "home_loan_interest",
    "donation": "donations",
}

# Max limits for deductions under old regime
DEDUCTION_LIMITS = {
    "deduction_80c": 150000,
    "deduction_80d": 75000,       # senior citizen max; general 25k — simplified
    "home_loan_interest": 200000,
    "donation": None,             # no cap here; 100%/50% rules ignored for simplicity
}


class ConsolidationService:
    """Merge statements + calculate tax"""

    # ──────────────── MERGE ────────────────

    @staticmethod
    def get_user_statements(db: Session, user_id: int, statement_ids: Optional[List[int]] = None):
        """Fetch user's processed statements, optionally filtered by IDs."""
        q = db.query(BankStatement).filter(
            BankStatement.user_id == user_id,
            BankStatement.processing_status == "completed"
        )
        if statement_ids:
            q = q.filter(BankStatement.id.in_(statement_ids))
        return q.order_by(BankStatement.statement_period_start).all()

    @staticmethod
    def merge_transactions(
        db: Session, user_id: int,
        statement_ids: Optional[List[int]] = None,
        financial_year: str = "2024-25"
    ) -> dict:
        """
        Pull all transactions from selected statements, deduplicate,
        and return a categorised summary.
        """
        statements = ConsolidationService.get_user_statements(db, user_id, statement_ids)
        if not statements:
            return {
                "financial_year": financial_year,
                "statements_merged": 0,
                "total_transactions": 0,
                "duplicates_removed": 0,
                "period_start": None, "period_end": None,
                "total_credit": 0, "total_debit": 0, "net_balance": 0,
                "category_breakdown": [],
            }

        stmt_ids = [s.id for s in statements]

        # Fetch all transactions from these statements
        txns = (
            db.query(Transaction)
            .filter(Transaction.statement_id.in_(stmt_ids))
            .order_by(Transaction.date)
            .all()
        )

        # Deduplicate: same date + description + debit + credit
        seen = set()
        unique_txns = []
        dupes = 0
        for t in txns:
            key = (
                t.date.strftime("%Y-%m-%d") if t.date else "",
                (t.description or "").strip().lower(),
                round(t.debit or 0, 2),
                round(t.credit or 0, 2),
            )
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            unique_txns.append(t)

        # Category breakdown
        cat_map: dict = {}
        total_credit = 0.0
        total_debit = 0.0
        for t in unique_txns:
            cat = t.category
            if hasattr(cat, "value"):
                cat = cat.value
            cat = str(cat).lower()
            if cat not in cat_map:
                cat_map[cat] = {"transaction_count": 0, "total_credit": 0, "total_debit": 0}
            cat_map[cat]["transaction_count"] += 1
            cat_map[cat]["total_credit"] += t.credit or 0
            cat_map[cat]["total_debit"] += t.debit or 0
            total_credit += t.credit or 0
            total_debit += t.debit or 0

        breakdown = []
        for cat, vals in sorted(cat_map.items()):
            breakdown.append({
                "category": cat,
                "transaction_count": vals["transaction_count"],
                "total_credit": round(vals["total_credit"], 2),
                "total_debit": round(vals["total_debit"], 2),
                "net_amount": round(vals["total_credit"] - vals["total_debit"], 2),
            })

        # Period range
        period_start = None
        period_end = None
        for s in statements:
            if s.statement_period_start:
                if period_start is None or s.statement_period_start < period_start:
                    period_start = s.statement_period_start
            if s.statement_period_end:
                if period_end is None or s.statement_period_end > period_end:
                    period_end = s.statement_period_end

        return {
            "financial_year": financial_year,
            "statements_merged": len(statements),
            "total_transactions": len(unique_txns),
            "duplicates_removed": dupes,
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "total_credit": round(total_credit, 2),
            "total_debit": round(total_debit, 2),
            "net_balance": round(total_credit - total_debit, 2),
            "category_breakdown": breakdown,
        }

    # ──────────────── TAX CALCULATION ────────────────

    @staticmethod
    def _income_from_breakdown(breakdown: list) -> dict:
        """Extract income & deduction amounts from category breakdown."""
        result = {
            "salary_income": 0, "interest_income": 0, "dividend_income": 0,
            "rental_income": 0, "capital_gains": 0, "business_income": 0,
            "other_income": 0,
            "deduction_80c": 0, "deduction_80d": 0,
            "home_loan_interest": 0, "donations": 0,
        }

        for item in breakdown:
            cat = item["category"]
            credit = item["total_credit"]
            debit = item["total_debit"]

            if cat in INCOME_CATEGORIES:
                result[INCOME_CATEGORIES[cat]] += credit
            elif cat in DEDUCTION_CATEGORIES:
                # Deductions are outflows (debits)
                result[DEDUCTION_CATEGORIES[cat]] += debit
            else:
                # uncategorized / transfer / expense → ignore for tax
                pass

        return result

    @staticmethod
    def _calc_old_regime(taxable_income: float) -> Tuple[List[dict], float]:
        """Old regime slabs (AY 2025-26, age < 60)"""
        slabs = [
            (250000, 0.00, "₹0 – ₹2,50,000", "Nil"),
            (250000, 0.05, "₹2,50,001 – ₹5,00,000", "5%"),
            (500000, 0.20, "₹5,00,001 – ₹10,00,000", "20%"),
            (float("inf"), 0.30, "Above ₹10,00,000", "30%"),
        ]
        return ConsolidationService._apply_slabs(taxable_income, slabs)

    @staticmethod
    def _calc_new_regime(taxable_income: float) -> Tuple[List[dict], float]:
        """New regime slabs (AY 2025-26, Section 115BAC)"""
        slabs = [
            (300000, 0.00, "₹0 – ₹3,00,000", "Nil"),
            (400000, 0.05, "₹3,00,001 – ₹7,00,000", "5%"),
            (300000, 0.10, "₹7,00,001 – ₹10,00,000", "10%"),
            (200000, 0.15, "₹10,00,001 – ₹12,00,000", "15%"),
            (300000, 0.20, "₹12,00,001 – ₹15,00,000", "20%"),
            (float("inf"), 0.30, "Above ₹15,00,000", "30%"),
        ]
        return ConsolidationService._apply_slabs(taxable_income, slabs)

    @staticmethod
    def _apply_slabs(income: float, slabs) -> Tuple[List[dict], float]:
        details = []
        remaining = income
        total_tax = 0.0
        for width, rate, label, rate_label in slabs:
            taxable_in_slab = min(remaining, width)
            if taxable_in_slab <= 0:
                break
            tax = taxable_in_slab * rate
            details.append({
                "slab": label,
                "rate": rate_label,
                "taxable_amount": round(taxable_in_slab, 2),
                "tax": round(tax, 2),
            })
            total_tax += tax
            remaining -= taxable_in_slab
        return details, round(total_tax, 2)

    @staticmethod
    def calculate_tax(
        db: Session, user_id: int,
        financial_year: str = "2024-25",
        tax_regime: str = "both",
        statement_ids: Optional[List[int]] = None,
    ) -> dict:
        """
        Calculate income tax from merged transactions.
        Returns result for old, new, or both regimes.
        """
        merged = ConsolidationService.merge_transactions(db, user_id, statement_ids, financial_year)
        income = ConsolidationService._income_from_breakdown(merged["category_breakdown"])

        gross = (
            income["salary_income"] + income["interest_income"] +
            income["dividend_income"] + income["rental_income"] +
            income["capital_gains"] + income["business_income"] +
            income["other_income"]
        )

        # Apply deduction caps (old regime only uses these)
        ded_80c = min(income["deduction_80c"], DEDUCTION_LIMITS["deduction_80c"])
        ded_80d = min(income["deduction_80d"], DEDUCTION_LIMITS["deduction_80d"])
        ded_hli = min(income["home_loan_interest"], DEDUCTION_LIMITS["home_loan_interest"])
        ded_don = income["donations"]
        standard_deduction = 75000   # Standard deduction for salaried (new regime AY 2025-26)

        def _compute(regime: str):
            if regime == "old":
                total_ded = ded_80c + ded_80d + ded_hli + ded_don + 50000  # old std ded 50k
                taxable = max(gross - total_ded, 0)
                slabs, tax_before = ConsolidationService._calc_old_regime(taxable)
                rebate = tax_before if taxable <= 500000 else 0
            else:
                total_ded = standard_deduction  # new regime: only standard deduction
                taxable = max(gross - total_ded, 0)
                slabs, tax_before = ConsolidationService._calc_new_regime(taxable)
                rebate = tax_before if taxable <= 700000 else 0

            tax_after = max(tax_before - rebate, 0)
            cess = round(tax_after * 0.04, 2)
            total_liability = round(tax_after + cess, 2)

            fy_start = int(financial_year.split("-")[0])
            ay = f"{fy_start + 1}-{int(financial_year.split('-')[1]) + 1:02d}"

            return {
                "financial_year": financial_year,
                "assessment_year": ay,
                "tax_regime": regime,
                **income,
                "gross_total_income": round(gross, 2),
                "total_deductions": round(total_ded, 2),
                "taxable_income": round(taxable, 2),
                "slab_details": slabs,
                "tax_before_cess": round(tax_before, 2),
                "rebate_87a": round(rebate, 2),
                "tax_after_rebate": round(tax_after, 2),
                "health_education_cess": cess,
                "total_tax_liability": total_liability,
            }

        if tax_regime == "both":
            old = _compute("old")
            new = _compute("new")
            recommended = "new" if new["total_tax_liability"] <= old["total_tax_liability"] else "old"
            better = old if recommended == "old" else new
            better["recommended_regime"] = recommended
            better["old_regime_tax"] = old["total_tax_liability"]
            better["new_regime_tax"] = new["total_tax_liability"]
            better["savings"] = round(abs(old["total_tax_liability"] - new["total_tax_liability"]), 2)
            # Return the recommended result with comparison fields
            return {"recommended": better, "old": old, "new": new}
        else:
            return _compute(tax_regime)

    # ──────────────── CREATE ITR FILING ────────────────

    @staticmethod
    def create_filing_from_merge(
        db: Session, user_id: int,
        financial_year: str, tax_regime: str,
        form_type: str = "ITR-1",
        statement_ids: Optional[List[int]] = None,
    ) -> dict:
        """
        Create an ITR filing + tax computation from merged statement data.
        """
        calc = ConsolidationService.calculate_tax(
            db, user_id, financial_year, tax_regime, statement_ids
        )
        # If 'both' was somehow passed, pick recommended
        if isinstance(calc, dict) and "recommended" in calc:
            calc = calc["recommended"]

        fy_start = int(financial_year.split("-")[0])
        ay = f"{fy_start + 1}-{int(financial_year.split('-')[1]) + 1:02d}"

        # Store income data as JSON for the filing
        filing_data = {
            "salary_income": calc["salary_income"],
            "interest_income": calc["interest_income"],
            "dividend_income": calc["dividend_income"],
            "rental_income": calc["rental_income"],
            "capital_gains": calc["capital_gains"],
            "business_income": calc["business_income"],
            "other_income": calc["other_income"],
            "gross_total_income": calc["gross_total_income"],
            "total_deductions": calc["total_deductions"],
            "taxable_income": calc["taxable_income"],
            "tax_regime": tax_regime,
        }

        # Create ITR filing
        filing = ITRFiling(
            user_id=user_id,
            assessment_year=ay,
            form_type=form_type,
            status="draft",
            review_status="pending_review",
            data=json.dumps(filing_data),
        )
        db.add(filing)
        db.flush()

        # Create tax computation
        comp = TaxComputation(
            itr_filing_id=filing.id,
            gross_total_income=calc["gross_total_income"],
            total_deductions=calc["total_deductions"],
            taxable_income=calc["taxable_income"],
            tax_on_total_income=calc["tax_before_cess"],
            rebate_87a=calc["rebate_87a"],
            health_education_cess=calc["health_education_cess"],
            total_tax_liability=calc["total_tax_liability"],
            tax_regime=tax_regime,
        )
        db.add(comp)
        db.commit()
        db.refresh(filing)
        db.refresh(comp)

        return {
            "message": "ITR filing created from merged statements",
            "filing_id": filing.id,
            "assessment_year": ay,
            "tax_regime": tax_regime,
            "total_tax_liability": calc["total_tax_liability"],
            "status": filing.status,
            "review_status": filing.review_status,
        }
