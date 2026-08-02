"""
Export service - generates PDF and JSON exports for ITR, Balance Sheet, Transactions
"""
import io
import json
from datetime import datetime
from typing import List, Optional

from fpdf import FPDF
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from models import (
    ITRFiling, TaxComputation, BalanceSheet, BalanceSheetItem,
    BankStatement, Transaction, User
)


class ITRExportPDF(FPDF):
    """Custom PDF class for ITR exports"""

    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Auto ITR - Income Tax Return', align='C', new_x="LMARGIN", new_y="NEXT")
        self.set_font('Helvetica', '', 8)
        self.cell(0, 5, f'Generated on {datetime.utcnow().strftime("%d-%b-%Y %H:%M UTC")}', align='C', new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    def section_title(self, title: str):
        self.set_font('Helvetica', 'B', 11)
        self.set_fill_color(10, 37, 64)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f'  {title}', fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def key_value_row(self, key: str, value: str):
        self.set_font('Helvetica', '', 10)
        self.cell(90, 7, key)
        self.set_font('Helvetica', 'B', 10)
        self.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")

    def amount_row(self, label: str, amount: float, bold: bool = False):
        style = 'B' if bold else ''
        self.set_font('Helvetica', style, 10)
        self.cell(120, 7, label)
        self.cell(0, 7, f'Rs. {amount:,.2f}', align='R', new_x="LMARGIN", new_y="NEXT")


class ExportService:
    """Service class for export operations"""

    # ─── ITR PDF ──────────────────────────────────────────────────────────

    @staticmethod
    def export_itr_pdf(db: Session, filing_id: int, user_id: int) -> bytes:
        """Generate PDF for an ITR filing"""
        filing = db.query(ITRFiling).filter(
            ITRFiling.id == filing_id, ITRFiling.user_id == user_id
        ).first()
        if not filing:
            raise HTTPException(status_code=404, detail="ITR filing not found")

        user = db.query(User).filter(User.id == user_id).first()
        comp = db.query(TaxComputation).filter(TaxComputation.itr_filing_id == filing.id).first()

        pdf = ITRExportPDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        # Filing info
        pdf.section_title('Filing Information')
        pdf.key_value_row('Assessment Year:', filing.assessment_year)
        pdf.key_value_row('Form Type:', filing.form_type)
        pdf.key_value_row('Status:', filing.status.upper())
        pdf.key_value_row('Review Status:', filing.review_status.replace('_', ' ').title())
        if filing.acknowledgement_number:
            pdf.key_value_row('Acknowledgement No:', filing.acknowledgement_number)
        if filing.filing_date:
            pdf.key_value_row('Filing Date:', filing.filing_date.strftime('%d-%b-%Y'))
        pdf.ln(4)

        # Taxpayer info
        pdf.section_title('Taxpayer Information')
        pdf.key_value_row('Name:', user.full_name or '-')
        pdf.key_value_row('Email:', user.email)
        pdf.key_value_row('PAN:', user.pan_number or 'Not Provided')
        pdf.key_value_row('Phone:', user.phone_number or '-')
        pdf.ln(4)

        # Tax computation
        if comp:
            pdf.section_title(f'Tax Computation ({comp.tax_regime.upper()} Regime)')
            pdf.amount_row('Gross Total Income', comp.gross_total_income)
            pdf.amount_row('Less: Total Deductions', comp.total_deductions)
            pdf.amount_row('Taxable Income', comp.taxable_income, bold=True)
            pdf.ln(2)
            pdf.amount_row('Tax on Total Income', comp.tax_on_total_income)
            if comp.rebate_87a > 0:
                pdf.amount_row('Less: Rebate u/s 87A', comp.rebate_87a)
            pdf.amount_row('Health & Education Cess (4%)', comp.health_education_cess)
            pdf.ln(1)
            pdf.set_draw_color(10, 37, 64)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(2)
            pdf.amount_row('TOTAL TAX PAYABLE', comp.total_tax_liability, bold=True)
            pdf.ln(4)

        # CA review
        if filing.ca_comments:
            pdf.section_title('CA Review Comments')
            pdf.set_font('Helvetica', '', 9)
            pdf.multi_cell(0, 5, filing.ca_comments)
            pdf.ln(4)

        # Disclaimer
        pdf.ln(6)
        pdf.set_font('Helvetica', 'I', 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 4,
            'Disclaimer: This document is auto-generated for reference only. '
            'Consult a qualified Chartered Accountant before filing your ITR. '
            'Figures may not reflect TDS, advance tax, or income from other sources.')

        return pdf.output()

    # ─── ITR JSON ─────────────────────────────────────────────────────────

    @staticmethod
    def export_itr_json(db: Session, filing_id: int, user_id: int) -> dict:
        """Generate JSON export for an ITR filing"""
        filing = db.query(ITRFiling).filter(
            ITRFiling.id == filing_id, ITRFiling.user_id == user_id
        ).first()
        if not filing:
            raise HTTPException(status_code=404, detail="ITR filing not found")

        user = db.query(User).filter(User.id == user_id).first()
        comp = db.query(TaxComputation).filter(TaxComputation.itr_filing_id == filing.id).first()

        result = {
            "export_date": datetime.utcnow().isoformat(),
            "filing": {
                "id": filing.id,
                "assessment_year": filing.assessment_year,
                "form_type": filing.form_type,
                "status": filing.status,
                "review_status": filing.review_status,
                "filing_date": filing.filing_date.isoformat() if filing.filing_date else None,
                "acknowledgement_number": filing.acknowledgement_number,
                "ca_comments": filing.ca_comments,
            },
            "taxpayer": {
                "name": user.full_name,
                "email": user.email,
                "pan": user.pan_number,
                "phone": user.phone_number,
            },
            "tax_computation": None,
        }

        if comp:
            result["tax_computation"] = {
                "tax_regime": comp.tax_regime,
                "gross_total_income": comp.gross_total_income,
                "total_deductions": comp.total_deductions,
                "taxable_income": comp.taxable_income,
                "tax_on_total_income": comp.tax_on_total_income,
                "rebate_87a": comp.rebate_87a,
                "health_education_cess": comp.health_education_cess,
                "total_tax_liability": comp.total_tax_liability,
            }

        return result

    # ─── Balance Sheet PDF ────────────────────────────────────────────────

    @staticmethod
    def export_balance_sheet_pdf(db: Session, bs_id: int, user_id: int) -> bytes:
        """Generate PDF for a balance sheet"""
        bs = db.query(BalanceSheet).filter(
            BalanceSheet.id == bs_id, BalanceSheet.user_id == user_id
        ).first()
        if not bs:
            raise HTTPException(status_code=404, detail="Balance sheet not found")

        user = db.query(User).filter(User.id == user_id).first()

        pdf = ITRExportPDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        type_label = bs.sheet_type.value.replace('_', ' ').title() if hasattr(bs.sheet_type, 'value') else str(bs.sheet_type)
        pdf.section_title(f'Balance Sheet - {type_label}')
        pdf.key_value_row('Financial Year:', bs.financial_year)
        pdf.key_value_row('Name:', bs.name or '-')
        pdf.key_value_row('Owner:', user.full_name or user.email)
        pdf.ln(4)

        # Summary
        pdf.section_title('Summary')
        pdf.amount_row('Total Assets', bs.total_assets, bold=True)
        pdf.amount_row('Total Liabilities', bs.total_liabilities, bold=True)
        if bs.total_equity > 0:
            pdf.amount_row('Total Equity', bs.total_equity, bold=True)
        pdf.amount_row('Net Worth', bs.total_assets - bs.total_liabilities, bold=True)
        pdf.ln(4)

        # Items by type
        items = db.query(BalanceSheetItem).filter(BalanceSheetItem.balance_sheet_id == bs.id).all()
        for item_type_label, item_type_val in [('Assets', 'asset'), ('Liabilities', 'liability'), ('Equity', 'equity')]:
            group = [i for i in items if (i.item_type.value if hasattr(i.item_type, 'value') else i.item_type) == item_type_val]
            if not group:
                continue
            pdf.section_title(item_type_label)
            # Table header
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(55, 7, 'Category', border=1)
            pdf.cell(45, 7, 'Subcategory', border=1)
            pdf.cell(50, 7, 'Description', border=1)
            pdf.cell(0, 7, 'Amount (Rs.)', border=1, align='R', new_x="LMARGIN", new_y="NEXT")
            pdf.set_font('Helvetica', '', 9)
            total = 0
            for i in group:
                pdf.cell(55, 6, (i.category or '-')[:28], border=1)
                pdf.cell(45, 6, (i.subcategory or '-')[:22], border=1)
                pdf.cell(50, 6, (i.description or '-')[:25], border=1)
                pdf.cell(0, 6, f'{i.amount:,.2f}', border=1, align='R', new_x="LMARGIN", new_y="NEXT")
                total += i.amount
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(150, 7, f'Total {item_type_label}', border=1)
            pdf.cell(0, 7, f'{total:,.2f}', border=1, align='R', new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        return pdf.output()

    # ─── Balance Sheet JSON ───────────────────────────────────────────────

    @staticmethod
    def export_balance_sheet_json(db: Session, bs_id: int, user_id: int) -> dict:
        """Generate JSON export for a balance sheet"""
        bs = db.query(BalanceSheet).filter(
            BalanceSheet.id == bs_id, BalanceSheet.user_id == user_id
        ).first()
        if not bs:
            raise HTTPException(status_code=404, detail="Balance sheet not found")

        items = db.query(BalanceSheetItem).filter(BalanceSheetItem.balance_sheet_id == bs.id).all()

        return {
            "export_date": datetime.utcnow().isoformat(),
            "balance_sheet": {
                "id": bs.id,
                "sheet_type": bs.sheet_type.value if hasattr(bs.sheet_type, 'value') else str(bs.sheet_type),
                "financial_year": bs.financial_year,
                "name": bs.name,
                "total_assets": bs.total_assets,
                "total_liabilities": bs.total_liabilities,
                "total_equity": bs.total_equity,
                "net_worth": bs.total_assets - bs.total_liabilities,
                "notes": bs.notes,
            },
            "items": [
                {
                    "id": i.id,
                    "item_type": i.item_type.value if hasattr(i.item_type, 'value') else str(i.item_type),
                    "category": i.category,
                    "subcategory": i.subcategory,
                    "description": i.description,
                    "amount": i.amount,
                }
                for i in items
            ],
        }

    # ─── Transactions PDF ─────────────────────────────────────────────────

    @staticmethod
    def export_transactions_pdf(db: Session, statement_id: int, user_id: int) -> bytes:
        """Generate PDF for transactions of a statement"""
        stmt = db.query(BankStatement).filter(
            BankStatement.id == statement_id, BankStatement.user_id == user_id
        ).first()
        if not stmt:
            raise HTTPException(status_code=404, detail="Statement not found")

        user = db.query(User).filter(User.id == user_id).first()
        txns = db.query(Transaction).filter(Transaction.statement_id == stmt.id).order_by(Transaction.date).all()

        pdf = ITRExportPDF()
        pdf.alias_nb_pages()
        pdf.add_page('L')  # Landscape for wide table

        pdf.section_title('Transaction Report')
        pdf.key_value_row('Statement:', stmt.filename)
        pdf.key_value_row('Bank:', stmt.bank_name or '-')
        pdf.key_value_row('Owner:', user.full_name or user.email)
        pdf.key_value_row('Total Transactions:', str(len(txns)))
        pdf.ln(4)

        # Table
        pdf.set_font('Helvetica', 'B', 8)
        col_w = [22, 70, 28, 28, 28, 35, 30, 28]
        headers = ['Date', 'Description', 'Debit', 'Credit', 'Balance', 'Category', 'Tax Rel.', 'FY']
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 6, h, border=1)
        pdf.ln()

        pdf.set_font('Helvetica', '', 7)
        total_debit = total_credit = 0
        for t in txns:
            date_str = t.date.strftime('%d-%m-%Y') if t.date else '-'
            desc = (t.description or '-')[:35]
            cat = (t.category.value if hasattr(t.category, 'value') else str(t.category or '')).replace('_', ' ')
            debit = t.debit or 0
            credit = t.credit or 0
            total_debit += debit
            total_credit += credit

            pdf.cell(col_w[0], 5, date_str, border=1)
            pdf.cell(col_w[1], 5, desc, border=1)
            pdf.cell(col_w[2], 5, f'{debit:,.2f}' if debit else '-', border=1, align='R')
            pdf.cell(col_w[3], 5, f'{credit:,.2f}' if credit else '-', border=1, align='R')
            pdf.cell(col_w[4], 5, f'{(t.balance or 0):,.2f}', border=1, align='R')
            pdf.cell(col_w[5], 5, cat[:18], border=1)
            pdf.cell(col_w[6], 5, 'Yes' if t.is_tax_relevant else 'No', border=1, align='C')
            pdf.cell(col_w[7], 5, t.financial_year or '-', border=1)
            pdf.ln()

        # Totals
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(col_w[0] + col_w[1], 6, 'TOTALS', border=1)
        pdf.cell(col_w[2], 6, f'{total_debit:,.2f}', border=1, align='R')
        pdf.cell(col_w[3], 6, f'{total_credit:,.2f}', border=1, align='R')
        pdf.cell(col_w[4] + col_w[5] + col_w[6] + col_w[7], 6, '', border=1)
        pdf.ln()

        return pdf.output()

    # ─── Transactions JSON ────────────────────────────────────────────────

    @staticmethod
    def export_transactions_json(db: Session, statement_id: int, user_id: int) -> dict:
        """Generate JSON export for transactions"""
        stmt = db.query(BankStatement).filter(
            BankStatement.id == statement_id, BankStatement.user_id == user_id
        ).first()
        if not stmt:
            raise HTTPException(status_code=404, detail="Statement not found")

        txns = db.query(Transaction).filter(Transaction.statement_id == stmt.id).order_by(Transaction.date).all()

        return {
            "export_date": datetime.utcnow().isoformat(),
            "statement": {
                "id": stmt.id,
                "filename": stmt.filename,
                "bank_name": stmt.bank_name,
                "account_number": stmt.account_number,
            },
            "total_transactions": len(txns),
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat() if t.date else None,
                    "description": t.description,
                    "debit": t.debit,
                    "credit": t.credit,
                    "balance": t.balance,
                    "category": t.category.value if hasattr(t.category, 'value') else str(t.category),
                    "is_tax_relevant": t.is_tax_relevant,
                    "financial_year": t.financial_year,
                    "notes": t.notes,
                }
                for t in txns
            ],
        }

    # ─── Merged Statement PDF ─────────────────────────────────────────────

    @staticmethod
    def export_merged_pdf(db: Session, user_id: int, statement_ids: List[int], financial_year: str) -> bytes:
        """Generate PDF for merged/consolidated bank statements"""
        from services.consolidation_service import ConsolidationService

        merged = ConsolidationService.merge_transactions(db, user_id, statement_ids, financial_year)
        user = db.query(User).filter(User.id == user_id).first()

        # Gather deduplicated transactions for the detailed table
        stmts = ConsolidationService.get_user_statements(db, user_id, statement_ids)
        stmt_ids = [s.id for s in stmts]
        all_txns = (
            db.query(Transaction)
            .filter(Transaction.statement_id.in_(stmt_ids))
            .order_by(Transaction.date)
            .all()
        ) if stmt_ids else []

        # Deduplicate (same logic as service)
        seen = set()
        unique_txns = []
        for t in all_txns:
            key = (
                t.date.strftime("%Y-%m-%d") if t.date else "",
                (t.description or "").strip().lower(),
                round(t.debit or 0, 2),
                round(t.credit or 0, 2),
            )
            if key not in seen:
                seen.add(key)
                unique_txns.append(t)

        pdf = ITRExportPDF()
        pdf.alias_nb_pages()
        pdf.add_page('L')

        # Title
        pdf.section_title(f'Merged Bank Statement - FY {financial_year}')
        pdf.key_value_row('Taxpayer:', user.full_name or user.email)
        pdf.key_value_row('PAN:', user.pan_number or 'Not Provided')
        pdf.key_value_row('Statements Merged:', str(merged["statements_merged"]))
        pdf.key_value_row('Total Transactions:', str(merged["total_transactions"]))
        pdf.key_value_row('Duplicates Removed:', str(merged["duplicates_removed"]))
        if merged["period_start"]:
            pdf.key_value_row('Period:', f'{merged["period_start"][:10]} to {merged["period_end"][:10]}')
        pdf.ln(4)

        # Summary
        pdf.section_title('Financial Summary')
        pdf.amount_row('Total Credits (Inflows)', merged["total_credit"])
        pdf.amount_row('Total Debits (Outflows)', merged["total_debit"])
        pdf.amount_row('Net Balance', merged["net_balance"], bold=True)
        pdf.ln(4)

        # Category breakdown
        if merged["category_breakdown"]:
            pdf.section_title('Category Breakdown')
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(60, 7, 'Category', border=1)
            pdf.cell(25, 7, 'Count', border=1, align='C')
            pdf.cell(40, 7, 'Credit (Rs.)', border=1, align='R')
            pdf.cell(40, 7, 'Debit (Rs.)', border=1, align='R')
            pdf.cell(40, 7, 'Net (Rs.)', border=1, align='R')
            pdf.ln()
            pdf.set_font('Helvetica', '', 9)
            for c in merged["category_breakdown"]:
                label = c["category"].replace("_", " ").title()
                label = label[:30].encode('latin-1', errors='replace').decode('latin-1')
                pdf.cell(60, 6, label, border=1)
                pdf.cell(25, 6, str(c["transaction_count"]), border=1, align='C')
                pdf.cell(40, 6, f'{c["total_credit"]:,.2f}', border=1, align='R')
                pdf.cell(40, 6, f'{c["total_debit"]:,.2f}', border=1, align='R')
                pdf.cell(40, 6, f'{c["net_amount"]:,.2f}', border=1, align='R')
                pdf.ln()
            pdf.ln(4)

        # Merged statements info
        if stmts:
            pdf.section_title('Source Statements')
            pdf.set_font('Helvetica', 'B', 9)
            pdf.cell(80, 7, 'Filename', border=1)
            pdf.cell(40, 7, 'Bank', border=1)
            pdf.cell(30, 7, 'Account', border=1)
            pdf.cell(40, 7, 'Period Start', border=1)
            pdf.cell(40, 7, 'Period End', border=1)
            pdf.ln()
            pdf.set_font('Helvetica', '', 8)
            for s in stmts:
                fname = (s.filename or '-')[:40].encode('latin-1', errors='replace').decode('latin-1')
                bname = (s.bank_name or '-')[:20].encode('latin-1', errors='replace').decode('latin-1')
                pdf.cell(80, 5, fname, border=1)
                pdf.cell(40, 5, bname, border=1)
                pdf.cell(30, 5, s.account_number or '-', border=1)
                pdf.cell(40, 5, s.statement_period_start.strftime('%d-%b-%Y') if s.statement_period_start else '-', border=1)
                pdf.cell(40, 5, s.statement_period_end.strftime('%d-%b-%Y') if s.statement_period_end else '-', border=1)
                pdf.ln()
            pdf.ln(4)

        # Transaction detail table — always included
        pdf.add_page('L')
        pdf.section_title(f'All Transactions ({len(unique_txns)} records)')

        if not unique_txns:
            pdf.set_font('Helvetica', '', 10)
            pdf.cell(0, 10, 'No transactions found for the selected statements.', new_x="LMARGIN", new_y="NEXT")
        else:
            pdf.set_font('Helvetica', 'B', 8)
            col_w = [22, 75, 28, 28, 28, 40, 28]
            headers = ['Date', 'Description', 'Debit', 'Credit', 'Balance', 'Category', 'FY']
            for i, h in enumerate(headers):
                pdf.cell(col_w[i], 6, h, border=1)
            pdf.ln()

            pdf.set_font('Helvetica', '', 7)
            total_debit = 0.0
            total_credit = 0.0
            for t in unique_txns:
                # Page break check
                if pdf.get_y() > 180:
                    pdf.add_page('L')
                    pdf.set_font('Helvetica', 'B', 8)
                    for i, h in enumerate(headers):
                        pdf.cell(col_w[i], 6, h, border=1)
                    pdf.ln()
                    pdf.set_font('Helvetica', '', 7)

                date_str = t.date.strftime('%d-%m-%Y') if t.date else '-'
                # Sanitize description for latin-1 encoding (fpdf2 core fonts)
                raw_desc = (t.description or '-')[:38]
                desc = raw_desc.encode('latin-1', errors='replace').decode('latin-1')
                cat = (t.category.value if hasattr(t.category, 'value') else str(t.category or '')).replace('_', ' ')
                cat = cat.encode('latin-1', errors='replace').decode('latin-1')
                debit = t.debit or 0
                credit = t.credit or 0
                total_debit += debit
                total_credit += credit
                pdf.cell(col_w[0], 5, date_str, border=1)
                pdf.cell(col_w[1], 5, desc, border=1)
                pdf.cell(col_w[2], 5, f'{debit:,.2f}' if debit else '-', border=1, align='R')
                pdf.cell(col_w[3], 5, f'{credit:,.2f}' if credit else '-', border=1, align='R')
                pdf.cell(col_w[4], 5, f'{(t.balance or 0):,.2f}', border=1, align='R')
                pdf.cell(col_w[5], 5, cat[:20], border=1)
                pdf.cell(col_w[6], 5, t.financial_year or '-', border=1)
                pdf.ln()

            # Totals row
            pdf.set_font('Helvetica', 'B', 8)
            pdf.cell(col_w[0] + col_w[1], 6, 'TOTALS', border=1)
            pdf.cell(col_w[2], 6, f'{total_debit:,.2f}', border=1, align='R')
            pdf.cell(col_w[3], 6, f'{total_credit:,.2f}', border=1, align='R')
            pdf.cell(col_w[4] + col_w[5] + col_w[6], 6, '', border=1)
            pdf.ln()

        return pdf.output()

    # ─── Merged Statement JSON ────────────────────────────────────────────

    @staticmethod
    def export_merged_json(db: Session, user_id: int, statement_ids: List[int], financial_year: str) -> dict:
        """Generate JSON export for merged/consolidated bank statements"""
        from services.consolidation_service import ConsolidationService

        merged = ConsolidationService.merge_transactions(db, user_id, statement_ids, financial_year)
        user = db.query(User).filter(User.id == user_id).first()

        # Gather deduplicated transactions
        stmts = ConsolidationService.get_user_statements(db, user_id, statement_ids)
        stmt_ids = [s.id for s in stmts]
        all_txns = (
            db.query(Transaction)
            .filter(Transaction.statement_id.in_(stmt_ids))
            .order_by(Transaction.date)
            .all()
        ) if stmt_ids else []

        seen = set()
        unique_txns = []
        for t in all_txns:
            key = (
                t.date.strftime("%Y-%m-%d") if t.date else "",
                (t.description or "").strip().lower(),
                round(t.debit or 0, 2),
                round(t.credit or 0, 2),
            )
            if key not in seen:
                seen.add(key)
                unique_txns.append(t)

        return {
            "export_date": datetime.utcnow().isoformat(),
            "financial_year": financial_year,
            "taxpayer": {
                "name": user.full_name,
                "email": user.email,
                "pan": user.pan_number,
            },
            "summary": {
                "statements_merged": merged["statements_merged"],
                "total_transactions": merged["total_transactions"],
                "duplicates_removed": merged["duplicates_removed"],
                "period_start": merged["period_start"],
                "period_end": merged["period_end"],
                "total_credit": merged["total_credit"],
                "total_debit": merged["total_debit"],
                "net_balance": merged["net_balance"],
            },
            "category_breakdown": merged["category_breakdown"],
            "source_statements": [
                {
                    "id": s.id,
                    "filename": s.filename,
                    "bank_name": s.bank_name,
                    "account_number": s.account_number,
                    "period_start": s.statement_period_start.isoformat() if s.statement_period_start else None,
                    "period_end": s.statement_period_end.isoformat() if s.statement_period_end else None,
                }
                for s in stmts
            ],
            "transactions": [
                {
                    "id": t.id,
                    "date": t.date.isoformat() if t.date else None,
                    "description": t.description,
                    "debit": t.debit,
                    "credit": t.credit,
                    "balance": t.balance,
                    "category": t.category.value if hasattr(t.category, 'value') else str(t.category),
                    "is_tax_relevant": t.is_tax_relevant,
                    "financial_year": t.financial_year,
                }
                for t in unique_txns
            ],
        }
