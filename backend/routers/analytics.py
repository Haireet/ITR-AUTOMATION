"""
Analytics router - provides income trends, expense analytics, tax insights
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime
from database import get_db
from models import User, Transaction, BankStatement, ITRFiling, TaxComputation, TransactionCategory
from utils.security import get_current_user
from pydantic import BaseModel

router = APIRouter()


# ============== Response Schemas ==============

class MonthlyTrend(BaseModel):
    month: str
    year: int
    income: float
    expense: float
    net: float

class CategoryBreakdown(BaseModel):
    category: str
    label: str
    amount: float
    percentage: float
    count: int

class TaxSavingSuggestion(BaseModel):
    section: str
    title: str
    description: str
    current_amount: float
    max_limit: float
    potential_savings: float
    priority: str  # high, medium, low

class YearComparison(BaseModel):
    financial_year: str
    gross_income: float
    total_deductions: float
    taxable_income: float
    tax_liability: float

class AnalyticsSummary(BaseModel):
    total_income: float
    total_expenses: float
    total_deductions: float
    estimated_tax: float
    transactions_count: int
    statements_count: int


# ============== Category Labels ==============

CATEGORY_LABELS = {
    'salary': 'Salary Income',
    'interest': 'Interest Income',
    'dividend': 'Dividend',
    'capital_gains': 'Capital Gains',
    'rental_income': 'Rental Income',
    'business_income': 'Business Income',
    'deduction_80c': 'Deduction 80C',
    'deduction_80d': 'Deduction 80D',
    'home_loan_interest': 'Home Loan Interest',
    'donation': 'Donation (80G)',
    'expense': 'Expense',
    'transfer': 'Fund Transfer',
    'uncategorized': 'Uncategorized'
}

INCOME_CATEGORIES = ['salary', 'interest', 'dividend', 'capital_gains', 'rental_income', 'business_income']
DEDUCTION_CATEGORIES = ['deduction_80c', 'deduction_80d', 'home_loan_interest', 'donation']
EXPENSE_CATEGORIES = ['expense', 'transfer', 'uncategorized']


# ============== Endpoints ==============

@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get overall analytics summary for the user"""
    
    # Get user's statements
    statements = db.query(BankStatement).filter(
        BankStatement.user_id == current_user.id,
        BankStatement.is_processed == True
    ).all()
    
    statement_ids = [s.id for s in statements]
    
    if not statement_ids:
        return AnalyticsSummary(
            total_income=0, total_expenses=0, total_deductions=0,
            estimated_tax=0, transactions_count=0, statements_count=0
        )
    
    # Build query for transactions
    query = db.query(Transaction).filter(Transaction.statement_id.in_(statement_ids))
    
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    
    transactions = query.all()
    
    total_income = sum(t.credit or 0 for t in transactions if t.category.value in INCOME_CATEGORIES)
    total_expenses = sum(t.debit or 0 for t in transactions if t.category.value in EXPENSE_CATEGORIES)
    total_deductions = sum(t.debit or 0 for t in transactions if t.category.value in DEDUCTION_CATEGORIES)
    
    # Simple tax estimation (new regime)
    taxable = max(0, total_income - total_deductions)
    estimated_tax = calculate_tax_new_regime(taxable)
    
    return AnalyticsSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        total_deductions=total_deductions,
        estimated_tax=estimated_tax,
        transactions_count=len(transactions),
        statements_count=len(statements)
    )


@router.get("/income-trends", response_model=List[MonthlyTrend])
async def get_income_trends(
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get monthly income and expense trends"""
    
    statements = db.query(BankStatement).filter(
        BankStatement.user_id == current_user.id,
        BankStatement.is_processed == True
    ).all()
    
    statement_ids = [s.id for s in statements]
    
    if not statement_ids:
        return []
    
    query = db.query(Transaction).filter(Transaction.statement_id.in_(statement_ids))
    
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    
    transactions = query.all()
    
    # Group by month
    monthly_data = {}
    for t in transactions:
        if not t.date:
            continue
        key = f"{t.date.year}-{t.date.month:02d}"
        if key not in monthly_data:
            monthly_data[key] = {'income': 0, 'expense': 0, 'year': t.date.year, 'month': t.date.month}
        
        if t.category.value in INCOME_CATEGORIES:
            monthly_data[key]['income'] += t.credit or 0
        elif t.category.value in EXPENSE_CATEGORIES:
            monthly_data[key]['expense'] += t.debit or 0
    
    # Sort by date and format
    trends = []
    for key in sorted(monthly_data.keys()):
        data = monthly_data[key]
        month_name = datetime(data['year'], data['month'], 1).strftime('%b %Y')
        trends.append(MonthlyTrend(
            month=month_name,
            year=data['year'],
            income=round(data['income'], 2),
            expense=round(data['expense'], 2),
            net=round(data['income'] - data['expense'], 2)
        ))
    
    return trends


@router.get("/expense-breakdown", response_model=List[CategoryBreakdown])
async def get_expense_breakdown(
    financial_year: Optional[str] = None,
    type: str = "expense",  # expense, income, deduction
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get expense/income breakdown by category"""
    
    statements = db.query(BankStatement).filter(
        BankStatement.user_id == current_user.id,
        BankStatement.is_processed == True
    ).all()
    
    statement_ids = [s.id for s in statements]
    
    if not statement_ids:
        return []
    
    query = db.query(Transaction).filter(Transaction.statement_id.in_(statement_ids))
    
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    
    # Filter by type
    if type == "income":
        categories = INCOME_CATEGORIES
    elif type == "deduction":
        categories = DEDUCTION_CATEGORIES
    else:
        categories = EXPENSE_CATEGORIES
    
    transactions = query.all()
    
    # Group by category
    category_totals = {}
    total_amount = 0
    
    for t in transactions:
        cat = t.category.value
        if cat not in categories:
            continue
        
        amount = t.credit if type == "income" else (t.debit or 0)
        if amount <= 0:
            continue
            
        if cat not in category_totals:
            category_totals[cat] = {'amount': 0, 'count': 0}
        category_totals[cat]['amount'] += amount
        category_totals[cat]['count'] += 1
        total_amount += amount
    
    # Format response
    breakdown = []
    for cat, data in sorted(category_totals.items(), key=lambda x: -x[1]['amount']):
        percentage = (data['amount'] / total_amount * 100) if total_amount > 0 else 0
        breakdown.append(CategoryBreakdown(
            category=cat,
            label=CATEGORY_LABELS.get(cat, cat),
            amount=round(data['amount'], 2),
            percentage=round(percentage, 1),
            count=data['count']
        ))
    
    return breakdown


@router.get("/tax-savings", response_model=List[TaxSavingSuggestion])
async def get_tax_savings_suggestions(
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get AI-based tax saving suggestions"""
    
    statements = db.query(BankStatement).filter(
        BankStatement.user_id == current_user.id,
        BankStatement.is_processed == True
    ).all()
    
    statement_ids = [s.id for s in statements]
    
    # Calculate current deductions
    current_deductions = {
        '80c': 0,
        '80d': 0,
        '24b': 0,
        '80g': 0
    }
    
    total_income = 0
    
    if statement_ids:
        query = db.query(Transaction).filter(Transaction.statement_id.in_(statement_ids))
        if financial_year:
            query = query.filter(Transaction.financial_year == financial_year)
        
        for t in query.all():
            if t.category.value in INCOME_CATEGORIES:
                total_income += t.credit or 0
            elif t.category.value == 'deduction_80c':
                current_deductions['80c'] += t.debit or 0
            elif t.category.value == 'deduction_80d':
                current_deductions['80d'] += t.debit or 0
            elif t.category.value == 'home_loan_interest':
                current_deductions['24b'] += t.debit or 0
            elif t.category.value == 'donation':
                current_deductions['80g'] += t.debit or 0
    
    suggestions = []
    
    # Section 80C - Max 1.5L
    max_80c = 150000
    if current_deductions['80c'] < max_80c:
        remaining = max_80c - current_deductions['80c']
        tax_rate = get_marginal_tax_rate(total_income)
        potential_savings = remaining * tax_rate
        
        suggestions.append(TaxSavingSuggestion(
            section="80C",
            title="Maximize Section 80C Investments",
            description=f"You can invest ₹{remaining:,.0f} more in ELSS, PPF, NSC, Tax-saving FD, or pay LIC premiums to claim full 80C deduction.",
            current_amount=current_deductions['80c'],
            max_limit=max_80c,
            potential_savings=round(potential_savings, 0),
            priority="high" if remaining > 100000 else "medium"
        ))
    
    # Section 80D - Health Insurance
    max_80d = 25000  # Self (50000 if senior citizen)
    if current_deductions['80d'] < max_80d:
        remaining = max_80d - current_deductions['80d']
        tax_rate = get_marginal_tax_rate(total_income)
        potential_savings = remaining * tax_rate
        
        suggestions.append(TaxSavingSuggestion(
            section="80D",
            title="Health Insurance Premium",
            description=f"Get health insurance for yourself and family. You can claim up to ₹{max_80d:,} (₹50,000 if senior citizen). Additional ₹50,000 for parents.",
            current_amount=current_deductions['80d'],
            max_limit=max_80d,
            potential_savings=round(potential_savings, 0),
            priority="high" if current_deductions['80d'] == 0 else "medium"
        ))
    
    # Section 24(b) - Home Loan Interest
    max_24b = 200000
    if current_deductions['24b'] < max_24b and current_deductions['24b'] > 0:
        remaining = max_24b - current_deductions['24b']
        suggestions.append(TaxSavingSuggestion(
            section="24(b)",
            title="Home Loan Interest Deduction",
            description=f"You're claiming ₹{current_deductions['24b']:,.0f} in home loan interest. Max limit is ₹2,00,000 for self-occupied property.",
            current_amount=current_deductions['24b'],
            max_limit=max_24b,
            potential_savings=0,
            priority="low"
        ))
    elif current_deductions['24b'] == 0:
        suggestions.append(TaxSavingSuggestion(
            section="24(b)",
            title="Consider Home Loan for Tax Benefits",
            description="If planning to buy a house, home loan interest up to ₹2,00,000 is deductible. Principal repayment also qualifies under 80C.",
            current_amount=0,
            max_limit=max_24b,
            potential_savings=round(max_24b * get_marginal_tax_rate(total_income), 0),
            priority="low"
        ))
    
    # NPS - Section 80CCD(1B)
    max_nps = 50000
    suggestions.append(TaxSavingSuggestion(
        section="80CCD(1B)",
        title="NPS Additional Deduction",
        description="Invest in National Pension System to claim additional ₹50,000 deduction over and above 80C limit.",
        current_amount=0,
        max_limit=max_nps,
        potential_savings=round(max_nps * get_marginal_tax_rate(total_income), 0),
        priority="medium"
    ))
    
    # Standard Deduction reminder
    suggestions.append(TaxSavingSuggestion(
        section="Standard",
        title="Standard Deduction (Salaried)",
        description="If you're salaried, you automatically get ₹50,000 standard deduction. Ensure it's reflected in your Form 16.",
        current_amount=50000,
        max_limit=50000,
        potential_savings=0,
        priority="low"
    ))
    
    # Sort by potential savings
    suggestions.sort(key=lambda x: -x.potential_savings)
    
    return suggestions


@router.get("/year-comparison", response_model=List[YearComparison])
async def get_year_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Compare tax data across financial years"""
    
    # Get all ITR filings with computations
    filings = db.query(ITRFiling).filter(
        ITRFiling.user_id == current_user.id
    ).order_by(ITRFiling.assessment_year).all()
    
    comparisons = []
    
    for filing in filings:
        computation = db.query(TaxComputation).filter(
            TaxComputation.itr_filing_id == filing.id
        ).first()
        
        if computation:
            # Convert assessment year to financial year
            ay = filing.assessment_year  # e.g., "2024-25"
            parts = ay.split('-')
            fy = f"{int(parts[0])-1}-{parts[1]}"
            
            comparisons.append(YearComparison(
                financial_year=fy,
                gross_income=computation.gross_total_income,
                total_deductions=computation.total_deductions,
                taxable_income=computation.taxable_income,
                tax_liability=computation.total_tax_liability
            ))
    
    # If no filings, try to compute from transactions
    if not comparisons:
        statements = db.query(BankStatement).filter(
            BankStatement.user_id == current_user.id,
            BankStatement.is_processed == True
        ).all()
        
        statement_ids = [s.id for s in statements]
        
        if statement_ids:
            # Get unique financial years from transactions
            years = db.query(Transaction.financial_year).filter(
                Transaction.statement_id.in_(statement_ids),
                Transaction.financial_year.isnot(None)
            ).distinct().all()
            
            for (fy,) in years:
                if not fy:
                    continue
                    
                transactions = db.query(Transaction).filter(
                    Transaction.statement_id.in_(statement_ids),
                    Transaction.financial_year == fy
                ).all()
                
                income = sum(t.credit or 0 for t in transactions if t.category.value in INCOME_CATEGORIES)
                deductions = sum(t.debit or 0 for t in transactions if t.category.value in DEDUCTION_CATEGORIES)
                taxable = max(0, income - deductions)
                tax = calculate_tax_new_regime(taxable)
                
                comparisons.append(YearComparison(
                    financial_year=fy,
                    gross_income=round(income, 2),
                    total_deductions=round(deductions, 2),
                    taxable_income=round(taxable, 2),
                    tax_liability=round(tax, 2)
                ))
    
    return sorted(comparisons, key=lambda x: x.financial_year)


# ============== Helper Functions ==============

def calculate_tax_new_regime(taxable_income: float) -> float:
    """Calculate tax under new regime (FY 2023-24 onwards)"""
    if taxable_income <= 300000:
        return 0
    elif taxable_income <= 600000:
        return (taxable_income - 300000) * 0.05
    elif taxable_income <= 900000:
        return 15000 + (taxable_income - 600000) * 0.10
    elif taxable_income <= 1200000:
        return 45000 + (taxable_income - 900000) * 0.15
    elif taxable_income <= 1500000:
        return 90000 + (taxable_income - 1200000) * 0.20
    else:
        return 150000 + (taxable_income - 1500000) * 0.30


def get_marginal_tax_rate(income: float) -> float:
    """Get marginal tax rate based on income (old regime approximation)"""
    if income <= 250000:
        return 0
    elif income <= 500000:
        return 0.05
    elif income <= 1000000:
        return 0.20
    else:
        return 0.30
