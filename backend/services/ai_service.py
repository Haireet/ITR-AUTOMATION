"""
AI Service - Smart categorization, chatbot, anomaly detection, tax optimization
Provides intelligent features for the Auto ITR platform
"""
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
from enum import Enum
import os
import json
from urllib import request as urlrequest, error as urlerror


# ============== Smart Categorization ML ==============

class SmartCategorizer:
    """
    Enhanced transaction categorizer using pattern matching, 
    context analysis, and learning from user corrections.
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.9
    MEDIUM_CONFIDENCE = 0.7
    LOW_CONFIDENCE = 0.5
    
    # Enhanced keyword patterns with weights
    CATEGORY_PATTERNS = {
        'salary': {
            'primary': ['salary', 'payroll', 'wages', 'sal cr', 'monthly pay', 'stipend'],
            'secondary': ['credit.*company', 'emp.*sal', 'pay.*slip', 'remuneration'],
            'negative': ['advance', 'loan', 'reimbursement'],
            'amount_range': (10000, 10000000),  # 10K to 1Cr
            'is_credit': True,
            'typical_day': list(range(25, 32)) + list(range(1, 6)),  # End/start of month
        },
        'interest': {
            'primary': ['interest', 'int cr', 'int credit', 'interest paid', 'fd interest'],
            'secondary': ['saving.*int', 'rd.*int', 'deposit.*int', 'bank.*int'],
            'negative': ['loan', 'emi', 'mortgage'],
            'is_credit': True,
        },
        'dividend': {
            'primary': ['dividend', 'div cr', 'interim div', 'final div'],
            'secondary': ['equity.*div', 'share.*div', 'mf.*div', 'mutual.*div'],
            'is_credit': True,
        },
        'rental_income': {
            'primary': ['rent', 'rental', 'lease', 'tenant'],
            'secondary': ['house.*rent', 'property.*rent', 'monthly.*rent'],
            'is_credit': True,
            'recurring': True,
        },
        'business_income': {
            'primary': ['business', 'professional', 'consulting', 'freelance', 'invoice'],
            'secondary': ['client.*payment', 'service.*fee', 'project.*payment'],
            'is_credit': True,
        },
        'deduction_80c': {
            'primary': ['ppf', 'epf', 'lic', 'elss', 'nsc', 'tax saver', 'nps'],
            'secondary': ['insurance.*premium', 'life.*insurance', 'provident.*fund', 'tuition'],
            'is_credit': False,
        },
        'deduction_80d': {
            'primary': ['health insurance', 'mediclaim', 'medical insurance'],
            'secondary': ['star health', 'max bupa', 'care health', 'health.*premium'],
            'is_credit': False,
        },
        'home_loan_interest': {
            'primary': ['home loan', 'housing loan', 'mortgage', 'emi'],
            'secondary': ['hdfc.*loan', 'sbi.*home', 'lic.*housing', 'property.*loan'],
            'is_credit': False,
            'recurring': True,
        },
        'donation': {
            'primary': ['donation', 'charity', 'ngo', 'trust'],
            'secondary': ['80g', 'charitable', 'relief fund', 'pm care'],
            'is_credit': False,
        },
        'expense': {
            'primary': ['shopping', 'purchase', 'bill', 'recharge', 'subscription'],
            'secondary': ['amazon', 'flipkart', 'swiggy', 'zomato', 'uber', 'ola'],
            'is_credit': False,
        },
        'transfer': {
            'primary': ['transfer', 'trf', 'self', 'own account'],
            'secondary': ['fund.*transfer', 'a/c.*transfer', 'between.*accounts'],
            'is_credit': None,  # Can be either
        },
    }
    
    def __init__(self):
        self.user_corrections = defaultdict(list)  # Learn from corrections
        
    def categorize(self, description: str, amount: float, is_credit: bool, 
                   date: datetime = None, user_id: int = None) -> Tuple[str, float, str]:
        """
        Categorize a transaction with confidence score and reasoning.
        Returns: (category, confidence, reason)
        """
        desc_lower = self._clean_description(description)
        
        best_match = ('uncategorized', 0.0, 'No pattern matched')
        
        for category, patterns in self.CATEGORY_PATTERNS.items():
            score, reason = self._calculate_match_score(
                desc_lower, amount, is_credit, date, category, patterns
            )
            
            if score > best_match[1]:
                best_match = (category, score, reason)
        
        # Check user corrections for similar transactions
        if user_id and best_match[1] < self.HIGH_CONFIDENCE:
            corrected = self._check_user_patterns(desc_lower, user_id)
            if corrected:
                return (corrected, 0.85, 'Based on your previous corrections')
        
        return best_match
    
    def _clean_description(self, desc: str) -> str:
        """Clean and normalize transaction description"""
        # Remove common noise
        noise_patterns = [
            r'\b(upi|neft|rtgs|imps|nach)\b[-/: ]*',
            r'\b\d{12,}\b',  # Long reference numbers
            r'[/-]\d{6,}',   # Date suffixes
        ]
        cleaned = desc.lower()
        for pattern in noise_patterns:
            cleaned = re.sub(pattern, ' ', cleaned)
        return ' '.join(cleaned.split())
    
    def _calculate_match_score(self, desc: str, amount: float, is_credit: bool,
                               date: datetime, category: str, patterns: dict) -> Tuple[float, str]:
        """Calculate match score for a category"""
        score = 0.0
        reasons = []
        
        # Check credit/debit match
        expected_credit = patterns.get('is_credit')
        if expected_credit is not None and expected_credit != is_credit:
            return (0.0, 'Credit/debit mismatch')
        
        # Primary keyword match (high weight)
        for keyword in patterns.get('primary', []):
            if keyword in desc:
                score += 0.5
                reasons.append(f'Matched keyword: {keyword}')
                break
        
        # Secondary pattern match (medium weight)
        for pattern in patterns.get('secondary', []):
            if re.search(pattern, desc):
                score += 0.25
                reasons.append(f'Matched pattern: {pattern}')
                break
        
        # Negative keyword check
        for neg in patterns.get('negative', []):
            if neg in desc:
                score -= 0.3
                reasons.append(f'Negative match: {neg}')
        
        # Amount range check
        amount_range = patterns.get('amount_range')
        if amount_range and amount_range[0] <= abs(amount) <= amount_range[1]:
            score += 0.1
            reasons.append('Amount in typical range')
        
        # Date pattern check (for salary)
        if date and patterns.get('typical_day'):
            if date.day in patterns['typical_day']:
                score += 0.1
                reasons.append('Date matches typical pattern')
        
        # Normalize score
        score = min(1.0, max(0.0, score))
        reason = '; '.join(reasons) if reasons else 'Low confidence match'
        
        return (score, reason)
    
    def _check_user_patterns(self, desc: str, user_id: int) -> Optional[str]:
        """Check if user has corrected similar transactions before"""
        corrections = self.user_corrections.get(user_id, [])
        for pattern, category in corrections:
            if pattern in desc:
                return category
        return None
    
    def learn_correction(self, user_id: int, description: str, correct_category: str):
        """Learn from user corrections"""
        # Extract key phrases from description
        key_words = self._extract_key_phrases(description)
        for phrase in key_words:
            self.user_corrections[user_id].append((phrase, correct_category))
    
    def _extract_key_phrases(self, desc: str) -> List[str]:
        """Extract meaningful key phrases from description"""
        cleaned = self._clean_description(desc)
        words = cleaned.split()
        # Return 2-3 word combinations
        phrases = []
        for i in range(len(words)):
            if len(words[i]) > 3:
                phrases.append(words[i])
            if i < len(words) - 1:
                phrases.append(f"{words[i]} {words[i+1]}")
        return phrases[:5]  # Limit to top 5
    
    def bulk_categorize(self, transactions: List[Dict]) -> List[Dict]:
        """Categorize multiple transactions with context awareness"""
        results = []
        
        # Analyze patterns across all transactions
        recurring = self._detect_recurring(transactions)
        
        for txn in transactions:
            category, confidence, reason = self.categorize(
                txn['description'],
                txn['amount'],
                txn['is_credit'],
                txn.get('date')
            )
            
            # Boost confidence for recurring patterns
            if txn['description'] in recurring:
                confidence = min(1.0, confidence + 0.1)
                reason += '; Recurring transaction detected'
            
            results.append({
                **txn,
                'category': category,
                'confidence': round(confidence, 2),
                'reason': reason
            })
        
        return results
    
    def _detect_recurring(self, transactions: List[Dict]) -> set:
        """Detect recurring transactions"""
        desc_counts = defaultdict(int)
        for txn in transactions:
            # Normalize description for comparison
            normalized = self._clean_description(txn['description'])[:50]
            desc_counts[normalized] += 1
        
        return {desc for desc, count in desc_counts.items() if count >= 2}


# ============== Tax Chatbot ==============

class TaxChatbot:
    """
    Indian tax chatbot with optional LLM integration and KB fallback.
    """
    
    KNOWLEDGE_BASE = {
        # Section 80C
        'what is 80c': {
            'answer': '''**Section 80C** allows deductions up to ₹1,50,000 for investments in:
• PPF (Public Provident Fund)
• ELSS (Equity Linked Savings Scheme)
• Life Insurance Premium
• EPF/VPF contributions
• NSC (National Savings Certificate)
• Tax-saving Fixed Deposits (5-year)
• Tuition fees for children
• Home loan principal repayment

💡 **Tip**: ELSS has the shortest lock-in (3 years) among 80C options.''',
            'keywords': ['80c', 'section 80c', 'deduction 80c', '1.5 lakh', '150000'],
        },
        
        # Section 80D
        'what is 80d': {
            'answer': '''**Section 80D** provides deductions for health insurance:
• Self/Family: Up to ₹25,000 (₹50,000 if senior citizen)
• Parents: Additional ₹25,000 (₹50,000 if senior citizen)
• Preventive Health Checkup: ₹5,000 (within above limits)

**Maximum Deduction**: ₹1,00,000 (if both self and parents are senior citizens)

💡 **Tip**: Premium for parents can be claimed even if they're not dependents.''',
            'keywords': ['80d', 'health insurance', 'medical insurance', 'mediclaim'],
        },
        
        # HRA
        'hra exemption': {
            'answer': '''**HRA Exemption** is the minimum of:
1. Actual HRA received
2. 50% of salary (metro) or 40% (non-metro)
3. Rent paid minus 10% of salary

**Documents needed**: Rent receipts, landlord PAN (if rent > ₹1 lakh/year)

💡 **Tip**: If you don't receive HRA, claim deduction under Section 80GG (max ₹5,000/month).''',
            'keywords': ['hra', 'house rent', 'rent exemption', 'house rent allowance'],
        },
        
        # New vs Old Regime
        'new vs old regime': {
            'answer': '''**Old Regime** (with deductions):
• Allows 80C, 80D, HRA, LTA etc.
• Higher tax rates
• Good if deductions > ₹3.75 lakh

**New Regime** (FY 2023-24):
• Lower tax rates
• Standard deduction ₹50,000 only
• No 80C/80D/HRA deductions
• Tax slabs: 0-3L: 0%, 3-6L: 5%, 6-9L: 10%, 9-12L: 15%, 12-15L: 20%, >15L: 30%

💡 **Tip**: Use our Tax Optimization feature to compare both regimes with your actual data!''',
            'keywords': ['old regime', 'new regime', 'tax regime', 'which regime', 'regime comparison'],
        },
        
        # Standard Deduction
        'standard deduction': {
            'answer': '''**Standard Deduction**: ₹50,000 flat deduction for salaried individuals.

✅ Available in BOTH old and new tax regimes (from FY 2023-24)
✅ No proof or investment required
✅ Automatically applied to salary income

💡 **Note**: Replaced transport allowance (₹19,200) and medical reimbursement (₹15,000).''',
            'keywords': ['standard deduction', '50000 deduction', 'salary deduction'],
        },
        
        # ITR Due Date
        'itr due date': {
            'answer': '''**ITR Filing Due Dates** (Non-audit cases):
• **31st July** - For FY 2023-24 (AY 2024-25)

**Late Filing**:
• After due date: ₹5,000 penalty (₹1,000 if income < ₹5 lakh)
• After 31st December: ₹10,000 penalty

💡 **Tip**: File early to get faster refunds and avoid last-minute rush!''',
            'keywords': ['due date', 'deadline', 'last date', 'filing date', 'when to file'],
        },
        
        # Section 24
        'home loan interest': {
            'answer': '''**Section 24(b)** - Home Loan Interest Deduction:
• **Self-occupied**: Up to ₹2,00,000/year
• **Let-out**: No limit (entire interest deductible)
• **Under construction**: Deduction available after possession (pre-EMI in 5 installments)

**Section 80EEA** (First-time buyers):
• Additional ₹1,50,000 if property value ≤ ₹45 lakh
• Loan sanctioned between April 2019 - March 2022

💡 **Tip**: Principal repayment qualifies under 80C (up to ₹1.5 lakh).''',
            'keywords': ['home loan', 'section 24', 'housing loan', 'mortgage interest', '80eea'],
        },
        
        # Capital Gains
        'capital gains tax': {
            'answer': '''**Capital Gains Tax Rates**:

**Equity/Mutual Funds**:
• STCG (< 1 year): 15%
• LTCG (> 1 year): 10% above ₹1 lakh

**Debt Funds** (from April 2023):
• All gains taxed at slab rate (no LTCG benefit)

**Property**:
• STCG (< 2 years): Slab rate
• LTCG (> 2 years): 20% with indexation

💡 **Tip**: LTCG on property can be saved by investing in 54EC bonds or new house (Section 54).''',
            'keywords': ['capital gains', 'ltcg', 'stcg', 'share profit', 'mutual fund gain'],
        },
        
        # Form 16
        'form 16': {
            'answer': '''**Form 16** is your TDS certificate from employer showing:
• Part A: TDS deducted and deposited
• Part B: Salary details, deductions claimed, tax computed

**When issued**: By June 15 of assessment year
**Use**: Pre-fills most details in ITR-1/ITR-2

💡 **Tip**: Upload Form 16 to our platform for automatic data extraction!''',
            'keywords': ['form 16', 'tds certificate', 'form16', 'salary certificate'],
        },
        
        # NPS
        'nps deduction': {
            'answer': '''**NPS Tax Benefits**:

**Section 80CCD(1)**: 
• Employee contribution up to 10% of salary
• Within 80C limit of ₹1.5 lakh

**Section 80CCD(1B)**:
• Additional ₹50,000 over 80C limit
• Available to all (salaried + self-employed)

**Section 80CCD(2)**:
• Employer contribution up to 10% of salary
• No upper limit, not part of 80C

💡 **Tip**: NPS gives ₹2 lakh+ extra deduction beyond 80C!''',
            'keywords': ['nps', 'national pension', '80ccd', 'pension scheme'],
        },
    }
    
    GREETING_PATTERNS = ['hi', 'hello', 'hey', 'help', 'start']
    
    def __init__(self):
        self.conversation_history = {}
        self.max_history_messages = 12
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1/chat/completions')
        self.request_timeout = int(os.getenv('OPENAI_TIMEOUT_SECONDS', '25'))
    
    def chat(self, user_id: int, message: str) -> Dict:
        """Process user message and return response"""
        clean_message = (message or '').strip()
        msg_lower = clean_message.lower()
        if not clean_message:
            return {
                'type': 'error',
                'message': 'Please type your question so I can help.',
                'suggestions': ['What is 80C?', 'Old vs new tax regime', 'ITR due date'],
                'mode': 'kb'
            }
        
        # Check for greetings
        if any(g == msg_lower for g in self.GREETING_PATTERNS):
            return self._greeting_response()

        # Use real AI when API key is configured
        if self.api_key:
            try:
                ai_answer = self._chat_with_llm(user_id, clean_message)
                return {
                    'type': 'ai_answer',
                    'message': ai_answer,
                    'confidence': 0.92,
                    'suggestions': self._get_ai_followups(clean_message),
                    'mode': 'llm'
                }
            except RuntimeError as e:
                print(f"LLM unavailable, falling back to knowledge base: {e}")
        
        # Search knowledge base
        best_match = self._find_best_match(msg_lower)
        
        if best_match:
            return {
                'type': 'answer',
                'message': best_match['answer'],
                'confidence': best_match['confidence'],
                'suggestions': self._get_related_topics(best_match['topic']),
                'mode': 'kb'
            }
        
        # No match found
        return {
            'type': 'not_found',
            'message': "I don't have specific information on that topic. Here are some things I can help with:",
            'suggestions': [
                'What is 80C?',
                'New vs Old regime',
                'HRA exemption',
                'Home loan interest deduction',
                'ITR due date'
            ],
            'mode': 'kb'
        }
    
    def _greeting_response(self) -> Dict:
        mode = "AI + Tax Knowledge" if self.api_key else "Tax Knowledge Base"
        return {
            'type': 'greeting',
            'message': f'''👋 Hello! I'm your **Tax Assistant** ({mode}). I can help you with:

• Tax deductions (80C, 80D, HRA, etc.)
• Old vs New tax regime
• ITR filing guidance
• Capital gains queries
• Home loan benefits

**Ask me anything about Indian income tax!**''',
            'suggestions': [
                'What is Section 80C?',
                'Which tax regime is better?',
                'How to claim HRA?',
                'Home loan tax benefits'
            ],
            'mode': 'llm' if self.api_key else 'kb'
        }

    def _chat_with_llm(self, user_id: int, user_message: str) -> str:
        system_prompt = (
            "You are an expert Indian Income Tax assistant for the Auto ITR app. "
            "Give practical, accurate, concise guidance for Indian taxpayers. "
            "Prefer clear steps and numbers. Mention assumptions when unsure. "
            "Do not provide harmful or illegal tax evasion instructions. "
            "If relevant, suggest using Auto ITR features like transaction categorization, "
            "tax optimization, and ITR review workflow."
        )

        history = self.conversation_history.get(user_id, [])
        messages = [{'role': 'system', 'content': system_prompt}] + history + [
            {'role': 'user', 'content': user_message}
        ]

        payload = {
            'model': self.model,
            'messages': messages,
            'temperature': 0.2,
            'max_tokens': 550
        }

        req = urlrequest.Request(
            self.base_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            },
            method='POST'
        )

        try:
            with urlrequest.urlopen(req, timeout=self.request_timeout) as resp:
                raw = resp.read().decode('utf-8')
        except urlerror.HTTPError as e:
            detail = e.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f'LLM HTTP error: {detail}')

        data = json.loads(raw)
        content = (
            data.get('choices', [{}])[0]
            .get('message', {})
            .get('content', '')
            .strip()
        )
        if not content:
            raise RuntimeError('Empty LLM response')

        new_history = history + [
            {'role': 'user', 'content': user_message},
            {'role': 'assistant', 'content': content}
        ]
        self.conversation_history[user_id] = new_history[-self.max_history_messages:]
        return content

    def _get_ai_followups(self, query: str) -> List[str]:
        q = query.lower()
        if '80c' in q or 'deduction' in q:
            return ['How much 80C can I still claim?', 'Should I choose old or new regime?']
        if 'regime' in q:
            return ['Compare tax for ₹12 lakh income', 'What deductions are ignored in new regime?']
        if 'itr' in q or 'file' in q:
            return ['Which ITR form should I use?', 'What documents should I keep ready?']
        return ['Show tax saving tips for my income', 'Explain this with an example']
    
    def _find_best_match(self, query: str) -> Optional[Dict]:
        """Find best matching answer from knowledge base"""
        best_score = 0
        best_match = None
        
        for topic, data in self.KNOWLEDGE_BASE.items():
            score = 0
            
            # Check keywords
            for keyword in data['keywords']:
                if keyword in query:
                    score += len(keyword.split())  # Multi-word keywords score higher
            
            # Check topic name
            if topic in query:
                score += 2
            
            if score > best_score:
                best_score = score
                best_match = {
                    'topic': topic,
                    'answer': data['answer'],
                    'confidence': min(1.0, score / 3)
                }
        
        return best_match if best_score > 0 else None
    
    def _get_related_topics(self, current_topic: str) -> List[str]:
        """Get related topic suggestions"""
        related = {
            'what is 80c': ['NPS deduction', 'Home loan interest'],
            'what is 80d': ['What is 80C?', 'Standard deduction'],
            'new vs old regime': ['What is 80C?', 'Standard deduction'],
            'home loan interest': ['What is 80C?', 'Capital gains tax'],
        }
        return related.get(current_topic, ['What is 80C?', 'New vs Old regime'])


# ============== Anomaly Detection ==============

class AnomalyDetector:
    """
    Detect unusual transactions that may need review
    """
    
    ANOMALY_TYPES = {
        'large_amount': 'Unusually large transaction',
        'unusual_time': 'Transaction at unusual time',
        'duplicate': 'Possible duplicate transaction',
        'category_mismatch': 'Category may be incorrect',
        'round_amount': 'Suspiciously round amount',
        'first_time_payee': 'First transaction with this payee',
        'frequency_spike': 'Unusual frequency of similar transactions',
    }
    
    def __init__(self, sensitivity: float = 0.7):
        """
        sensitivity: 0.0 (less alerts) to 1.0 (more alerts)
        """
        self.sensitivity = sensitivity
    
    def detect_anomalies(self, transactions: List[Dict], 
                         historical_transactions: List[Dict] = None) -> List[Dict]:
        """
        Analyze transactions and flag anomalies
        Returns transactions with anomaly flags
        """
        if not transactions:
            return []
        
        # Build statistical baseline
        amounts = [abs(t.get('amount', t.get('credit', 0) or t.get('debit', 0))) 
                   for t in (historical_transactions or transactions)]
        
        if len(amounts) > 5:
            mean_amount = statistics.mean(amounts)
            std_amount = statistics.stdev(amounts)
        else:
            mean_amount = sum(amounts) / len(amounts) if amounts else 0
            std_amount = mean_amount * 0.5
        
        results = []
        seen_transactions = {}
        
        for txn in transactions:
            anomalies = []
            
            amount = abs(txn.get('amount', txn.get('credit', 0) or txn.get('debit', 0)))
            desc = txn.get('description', '').lower()
            date = txn.get('date')
            
            # 1. Large amount detection
            if std_amount > 0:
                z_score = (amount - mean_amount) / std_amount
                threshold = 3 - (self.sensitivity * 1.5)  # 1.5 to 3 based on sensitivity
                if z_score > threshold:
                    anomalies.append({
                        'type': 'large_amount',
                        'message': f'Amount ₹{amount:,.0f} is {z_score:.1f}x standard deviations above average',
                        'severity': 'high' if z_score > 4 else 'medium'
                    })
            
            # 2. Round amount detection (potential fake/estimated entries)
            if amount > 10000 and amount % 10000 == 0:
                anomalies.append({
                    'type': 'round_amount',
                    'message': 'Unusually round amount - verify if correct',
                    'severity': 'low'
                })
            
            # 3. Duplicate detection
            txn_key = f"{amount}_{desc[:30]}_{date}"
            if txn_key in seen_transactions:
                anomalies.append({
                    'type': 'duplicate',
                    'message': 'Possible duplicate of earlier transaction',
                    'severity': 'high'
                })
            seen_transactions[txn_key] = True
            
            # 4. Category mismatch detection
            is_credit = txn.get('credit', 0) > 0
            category = txn.get('category', 'uncategorized')
            
            credit_categories = ['salary', 'interest', 'dividend', 'rental_income', 'business_income']
            debit_categories = ['expense', 'deduction_80c', 'deduction_80d', 'home_loan_interest', 'donation']
            
            if is_credit and category in debit_categories:
                anomalies.append({
                    'type': 'category_mismatch',
                    'message': f'Credit transaction categorized as {category} (typically debit)',
                    'severity': 'medium'
                })
            elif not is_credit and category in credit_categories:
                anomalies.append({
                    'type': 'category_mismatch',
                    'message': f'Debit transaction categorized as {category} (typically credit)',
                    'severity': 'medium'
                })
            
            # 5. Unusual keywords
            suspicious_keywords = ['cash', 'atm withdrawal', 'self cheque']
            if any(kw in desc for kw in suspicious_keywords) and amount > 50000:
                anomalies.append({
                    'type': 'large_cash',
                    'message': 'Large cash transaction - may need documentation',
                    'severity': 'medium'
                })
            
            results.append({
                **txn,
                'anomalies': anomalies,
                'has_anomaly': len(anomalies) > 0,
                'anomaly_count': len(anomalies),
                'max_severity': max([a['severity'] for a in anomalies], 
                                   key=lambda x: {'high': 3, 'medium': 2, 'low': 1}.get(x, 0),
                                   default='none')
            })
        
        return results
    
    def get_anomaly_summary(self, transactions: List[Dict]) -> Dict:
        """Get summary of all anomalies"""
        flagged = [t for t in transactions if t.get('has_anomaly')]
        
        by_type = defaultdict(int)
        by_severity = {'high': 0, 'medium': 0, 'low': 0}
        
        for txn in flagged:
            for anomaly in txn.get('anomalies', []):
                by_type[anomaly['type']] += 1
                by_severity[anomaly['severity']] += 1
        
        return {
            'total_transactions': len(transactions),
            'flagged_count': len(flagged),
            'flagged_percentage': round(len(flagged) / len(transactions) * 100, 1) if transactions else 0,
            'by_type': dict(by_type),
            'by_severity': by_severity,
            'high_priority': [t for t in flagged if t.get('max_severity') == 'high']
        }


# ============== Tax Optimization ==============

class TaxOptimizer:
    """
    Compare old vs new tax regime and recommend optimal choice
    """
    
    # New Regime Slabs (FY 2023-24 onwards)
    NEW_REGIME_SLABS = [
        (300000, 0.00),
        (600000, 0.05),
        (900000, 0.10),
        (1200000, 0.15),
        (1500000, 0.20),
        (float('inf'), 0.30),
    ]
    
    # Old Regime Slabs
    OLD_REGIME_SLABS = [
        (250000, 0.00),
        (500000, 0.05),
        (1000000, 0.20),
        (float('inf'), 0.30),
    ]
    
    def optimize(self, gross_income: float, deductions: Dict) -> Dict:
        """
        Compare both regimes and recommend the better one
        
        deductions: {
            '80c': float,
            '80d': float,
            'hra': float,
            'home_loan': float,
            'nps': float,
            'standard': float,
            'other': float
        }
        """
        # Calculate taxable income for both regimes
        total_deductions_old = sum(deductions.values())
        
        # New regime only allows standard deduction
        standard_deduction = 50000
        
        taxable_old = max(0, gross_income - total_deductions_old)
        taxable_new = max(0, gross_income - standard_deduction)
        
        # Calculate tax for both
        tax_old = self._calculate_tax(taxable_old, self.OLD_REGIME_SLABS)
        tax_new = self._calculate_tax(taxable_new, self.NEW_REGIME_SLABS)
        
        # Apply rebate u/s 87A
        tax_old = self._apply_rebate_old(taxable_old, tax_old)
        tax_new = self._apply_rebate_new(taxable_new, tax_new)
        
        # Add cess
        tax_old_with_cess = tax_old * 1.04
        tax_new_with_cess = tax_new * 1.04
        
        savings = tax_old_with_cess - tax_new_with_cess
        recommended = 'new' if savings > 0 else 'old'
        
        # Calculate break-even deduction
        break_even = self._calculate_break_even(gross_income)
        
        return {
            'gross_income': gross_income,
            'old_regime': {
                'total_deductions': total_deductions_old,
                'deductions_breakdown': deductions,
                'taxable_income': taxable_old,
                'tax_before_cess': tax_old,
                'cess': tax_old * 0.04,
                'total_tax': round(tax_old_with_cess, 0)
            },
            'new_regime': {
                'total_deductions': standard_deduction,
                'taxable_income': taxable_new,
                'tax_before_cess': tax_new,
                'cess': tax_new * 0.04,
                'total_tax': round(tax_new_with_cess, 0)
            },
            'recommendation': {
                'regime': recommended,
                'savings': abs(round(savings, 0)),
                'reason': self._get_recommendation_reason(recommended, total_deductions_old, break_even)
            },
            'break_even_deduction': break_even,
            'tips': self._get_optimization_tips(gross_income, deductions, recommended)
        }
    
    def _calculate_tax(self, income: float, slabs: List[Tuple]) -> float:
        """Calculate tax based on slab rates"""
        tax = 0
        prev_limit = 0
        
        for limit, rate in slabs:
            if income <= prev_limit:
                break
            taxable_in_slab = min(income, limit) - prev_limit
            tax += taxable_in_slab * rate
            prev_limit = limit
        
        return tax
    
    def _apply_rebate_old(self, taxable: float, tax: float) -> float:
        """Apply rebate u/s 87A for old regime"""
        if taxable <= 500000:
            return max(0, tax - 12500)
        return tax
    
    def _apply_rebate_new(self, taxable: float, tax: float) -> float:
        """Apply rebate u/s 87A for new regime"""
        if taxable <= 700000:
            return max(0, tax - 25000)
        return tax
    
    def _calculate_break_even(self, gross_income: float) -> float:
        """Calculate deduction amount where both regimes give same tax"""
        # Approximate break-even calculation
        if gross_income <= 700000:
            return 0  # New regime likely better due to higher rebate
        elif gross_income <= 1000000:
            return gross_income * 0.15
        elif gross_income <= 1500000:
            return gross_income * 0.20
        else:
            return gross_income * 0.25
    
    def _get_recommendation_reason(self, regime: str, deductions: float, break_even: float) -> str:
        if regime == 'new':
            if deductions < break_even:
                return f"Your deductions (₹{deductions:,.0f}) are below the break-even point (₹{break_even:,.0f}). New regime saves you tax."
            else:
                return "New regime offers lower tax rates that outweigh your deductions."
        else:
            return f"Your deductions (₹{deductions:,.0f}) exceed break-even (₹{break_even:,.0f}). Old regime saves you tax."
    
    def _get_optimization_tips(self, income: float, deductions: Dict, regime: str) -> List[str]:
        tips = []
        
        if regime == 'old':
            # Check if 80C is maxed
            if deductions.get('80c', 0) < 150000:
                gap = 150000 - deductions.get('80c', 0)
                tips.append(f"💡 Invest ₹{gap:,.0f} more in 80C (PPF/ELSS) to maximize deductions")
            
            # Check 80D
            if deductions.get('80d', 0) < 25000:
                tips.append("💡 Get health insurance to claim up to ₹25,000 under 80D")
            
            # NPS
            if deductions.get('nps', 0) == 0:
                tips.append("💡 Invest in NPS for additional ₹50,000 deduction under 80CCD(1B)")
        
        else:  # New regime
            tips.append("✅ New regime requires no investment proofs - simpler filing")
            if income > 1500000:
                tips.append("💡 Consider voluntary EPF/NPS for retirement savings (no tax benefit in new regime)")
        
        return tips


# ============== Factory/Singleton Instances ==============

_categorizer = None
_chatbot = None
_anomaly_detector = None
_optimizer = None


def get_categorizer() -> SmartCategorizer:
    global _categorizer
    if _categorizer is None:
        _categorizer = SmartCategorizer()
    return _categorizer


def get_chatbot() -> TaxChatbot:
    global _chatbot
    if _chatbot is None:
        _chatbot = TaxChatbot()
    return _chatbot


def get_anomaly_detector(sensitivity: float = 0.7) -> AnomalyDetector:
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector(sensitivity)
    return _anomaly_detector


def get_optimizer() -> TaxOptimizer:
    global _optimizer
    if _optimizer is None:
        _optimizer = TaxOptimizer()
    return _optimizer
