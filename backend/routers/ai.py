"""
AI Router - Smart categorization, chatbot, anomaly detection, tax optimization
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models import User, Transaction, BankStatement
from utils.security import get_current_user
from services.ai_service import (
    get_categorizer, get_chatbot, get_anomaly_detector, get_optimizer
)

router = APIRouter()


# ============== Request/Response Schemas ==============

class CategorizationRequest(BaseModel):
    description: str
    amount: float
    is_credit: bool
    date: Optional[str] = None

class CategorizationResponse(BaseModel):
    category: str
    confidence: float
    reason: str

class BulkCategorizationRequest(BaseModel):
    transactions: List[CategorizationRequest]

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    type: str
    message: str
    confidence: Optional[float] = None
    suggestions: List[str] = []
    mode: Optional[str] = None

class AnomalyRequest(BaseModel):
    statement_id: Optional[int] = None

class TaxOptimizationRequest(BaseModel):
    gross_income: float
    deductions: dict  # {'80c': 150000, '80d': 25000, etc.}

class LearnCorrectionRequest(BaseModel):
    description: str
    correct_category: str


# ============== Endpoints ==============

@router.post("/categorize", response_model=CategorizationResponse)
async def categorize_transaction(
    request: CategorizationRequest,
    current_user: User = Depends(get_current_user)
):
    """Smart categorize a single transaction"""
    categorizer = get_categorizer()
    
    from datetime import datetime
    date = None
    if request.date:
        try:
            date = datetime.fromisoformat(request.date)
        except:
            pass
    
    category, confidence, reason = categorizer.categorize(
        description=request.description,
        amount=request.amount,
        is_credit=request.is_credit,
        date=date,
        user_id=current_user.id
    )
    
    return CategorizationResponse(
        category=category,
        confidence=confidence,
        reason=reason
    )


@router.post("/categorize-bulk")
async def categorize_bulk(
    request: BulkCategorizationRequest,
    current_user: User = Depends(get_current_user)
):
    """Categorize multiple transactions with context awareness"""
    categorizer = get_categorizer()
    
    transactions = [
        {
            'description': t.description,
            'amount': t.amount,
            'is_credit': t.is_credit,
            'date': t.date
        }
        for t in request.transactions
    ]
    
    results = categorizer.bulk_categorize(transactions)
    return {'results': results}


@router.post("/learn-correction")
async def learn_from_correction(
    request: LearnCorrectionRequest,
    current_user: User = Depends(get_current_user)
):
    """Learn from user's manual category correction"""
    categorizer = get_categorizer()
    categorizer.learn_correction(
        user_id=current_user.id,
        description=request.description,
        correct_category=request.correct_category
    )
    return {'message': 'Correction learned successfully'}


@router.post("/auto-categorize/{statement_id}")
async def auto_categorize_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-categorize all uncategorized transactions in a statement"""
    # Verify statement ownership
    statement = db.query(BankStatement).filter(
        BankStatement.id == statement_id,
        BankStatement.user_id == current_user.id
    ).first()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    # Get uncategorized transactions
    transactions = db.query(Transaction).filter(
        Transaction.statement_id == statement_id,
        Transaction.category == 'uncategorized'
    ).all()
    
    if not transactions:
        return {'message': 'No uncategorized transactions found', 'updated': 0}
    
    categorizer = get_categorizer()
    updated = 0
    
    for txn in transactions:
        category, confidence, reason = categorizer.categorize(
            description=txn.description,
            amount=txn.credit or txn.debit or 0,
            is_credit=bool(txn.credit and txn.credit > 0),
            date=txn.date,
            user_id=current_user.id
        )
        
        # Only update if confidence is above threshold
        if confidence >= 0.5:
            txn.category = category
            txn.confidence_score = confidence
            txn.manually_labeled = False
            updated += 1
    
    db.commit()
    
    return {
        'message': f'Auto-categorized {updated} transactions',
        'total': len(transactions),
        'updated': updated,
        'skipped': len(transactions) - updated
    }


# ============== Chatbot Endpoints ==============

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Chat with the tax assistant chatbot"""
    chatbot = get_chatbot()
    response = chatbot.chat(current_user.id, request.message)
    
    return ChatResponse(
        type=response['type'],
        message=response['message'],
        confidence=response.get('confidence'),
        suggestions=response.get('suggestions', []),
        mode=response.get('mode')
    )


@router.get("/chat/topics")
async def get_chat_topics():
    """Get list of topics the chatbot can help with"""
    return {
        'topics': [
            {'id': '80c', 'title': 'Section 80C Deductions', 'query': 'What is 80C?'},
            {'id': '80d', 'title': 'Health Insurance (80D)', 'query': 'What is 80D?'},
            {'id': 'hra', 'title': 'HRA Exemption', 'query': 'HRA exemption'},
            {'id': 'regime', 'title': 'Old vs New Regime', 'query': 'New vs old regime'},
            {'id': 'home_loan', 'title': 'Home Loan Benefits', 'query': 'Home loan interest'},
            {'id': 'capital_gains', 'title': 'Capital Gains Tax', 'query': 'Capital gains tax'},
            {'id': 'nps', 'title': 'NPS Benefits', 'query': 'NPS deduction'},
            {'id': 'due_date', 'title': 'ITR Due Dates', 'query': 'ITR due date'},
            {'id': 'form16', 'title': 'Form 16', 'query': 'Form 16'},
            {'id': 'standard', 'title': 'Standard Deduction', 'query': 'Standard deduction'},
        ]
    }


# ============== Anomaly Detection Endpoints ==============

@router.get("/anomalies/{statement_id}")
async def detect_anomalies(
    statement_id: int,
    sensitivity: float = 0.7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Detect anomalies in a statement's transactions"""
    # Verify statement ownership
    statement = db.query(BankStatement).filter(
        BankStatement.id == statement_id,
        BankStatement.user_id == current_user.id
    ).first()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Statement not found")
    
    # Get transactions
    transactions = db.query(Transaction).filter(
        Transaction.statement_id == statement_id
    ).all()
    
    if not transactions:
        return {'anomalies': [], 'summary': {}}
    
    # Convert to dict format
    txn_list = [
        {
            'id': t.id,
            'description': t.description,
            'amount': t.credit or t.debit or 0,
            'credit': t.credit,
            'debit': t.debit,
            'date': t.date.isoformat() if t.date else None,
            'category': t.category.value if t.category else 'uncategorized'
        }
        for t in transactions
    ]
    
    # Get historical transactions for better baseline
    historical = db.query(Transaction).join(BankStatement).filter(
        BankStatement.user_id == current_user.id
    ).limit(500).all()
    
    hist_list = [
        {'amount': t.credit or t.debit or 0}
        for t in historical
    ]
    
    detector = get_anomaly_detector(sensitivity)
    results = detector.detect_anomalies(txn_list, hist_list)
    summary = detector.get_anomaly_summary(results)
    
    # Filter to only anomalies
    anomalies = [r for r in results if r['has_anomaly']]
    
    return {
        'anomalies': anomalies,
        'summary': summary
    }


@router.get("/anomalies-all")
async def detect_all_anomalies(
    sensitivity: float = 0.7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Detect anomalies across all user's transactions"""
    # Get all user's transactions
    transactions = db.query(Transaction).join(BankStatement).filter(
        BankStatement.user_id == current_user.id
    ).order_by(Transaction.date.desc()).limit(1000).all()
    
    if not transactions:
        return {'anomalies': [], 'summary': {'total_transactions': 0, 'flagged_count': 0}}
    
    txn_list = [
        {
            'id': t.id,
            'statement_id': t.statement_id,
            'description': t.description,
            'amount': t.credit or t.debit or 0,
            'credit': t.credit,
            'debit': t.debit,
            'date': t.date.isoformat() if t.date else None,
            'category': t.category.value if t.category else 'uncategorized'
        }
        for t in transactions
    ]
    
    detector = get_anomaly_detector(sensitivity)
    results = detector.detect_anomalies(txn_list)
    summary = detector.get_anomaly_summary(results)
    
    anomalies = [r for r in results if r['has_anomaly']]
    
    return {
        'anomalies': anomalies[:50],  # Limit response size
        'summary': summary
    }


# ============== Tax Optimization Endpoints ==============

@router.post("/optimize-tax")
async def optimize_tax(
    request: TaxOptimizationRequest,
    current_user: User = Depends(get_current_user)
):
    """Compare old vs new tax regime and get recommendation"""
    optimizer = get_optimizer()
    
    # Ensure all deduction keys have defaults
    deductions = {
        '80c': request.deductions.get('80c', 0),
        '80d': request.deductions.get('80d', 0),
        'hra': request.deductions.get('hra', 0),
        'home_loan': request.deductions.get('home_loan', 0),
        'nps': request.deductions.get('nps', 0),
        'standard': request.deductions.get('standard', 50000),
        'other': request.deductions.get('other', 0),
    }
    
    result = optimizer.optimize(request.gross_income, deductions)
    return result


@router.get("/optimize-tax-auto")
async def auto_optimize_tax(
    financial_year: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Auto-calculate tax optimization based on user's transaction data"""
    # Get user's statements
    statements = db.query(BankStatement).filter(
        BankStatement.user_id == current_user.id,
        BankStatement.is_processed == True
    ).all()
    
    statement_ids = [s.id for s in statements]
    
    if not statement_ids:
        raise HTTPException(status_code=404, detail="No processed statements found")
    
    # Query transactions
    query = db.query(Transaction).filter(Transaction.statement_id.in_(statement_ids))
    
    if financial_year:
        query = query.filter(Transaction.financial_year == financial_year)
    
    transactions = query.all()
    
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions found")
    
    # Calculate income and deductions from transactions
    income_categories = ['salary', 'interest', 'dividend', 'rental_income', 'business_income', 'capital_gains']
    
    gross_income = sum(
        t.credit or 0 
        for t in transactions 
        if t.category and t.category.value in income_categories
    )
    
    deductions = {
        '80c': sum(t.debit or 0 for t in transactions if t.category and t.category.value == 'deduction_80c'),
        '80d': sum(t.debit or 0 for t in transactions if t.category and t.category.value == 'deduction_80d'),
        'home_loan': sum(t.debit or 0 for t in transactions if t.category and t.category.value == 'home_loan_interest'),
        'hra': 0,  # Would need separate HRA data
        'nps': 0,
        'standard': 50000,
        'other': sum(t.debit or 0 for t in transactions if t.category and t.category.value == 'donation'),
    }
    
    optimizer = get_optimizer()
    result = optimizer.optimize(gross_income, deductions)
    
    return {
        **result,
        'data_source': 'transactions',
        'financial_year': financial_year or 'all',
        'transactions_analyzed': len(transactions)
    }
