"""
Transaction classification service - Rule-based categorization
Deterministic keyword matching for tax-relevant categories

Indian bank statement aware — handles UPI/NEFT/IMPS/RTGS prefixes,
common narration formats, and avoids false-positive "transfer" matches.
"""
import re
from typing import Optional, Tuple, List
from enum import Enum


class TransactionCategory(str, Enum):
    """Transaction categories for tax classification"""
    SALARY = "salary"
    INTEREST = "interest"
    DIVIDEND = "dividend"
    CAPITAL_GAINS = "capital_gains"
    RENTAL_INCOME = "rental_income"
    BUSINESS_INCOME = "business_income"
    DEDUCTION_80C = "deduction_80c"
    DEDUCTION_80D = "deduction_80d"
    HOME_LOAN_INTEREST = "home_loan_interest"
    DONATION = "donation"
    EXPENSE = "expense"
    TRANSFER = "transfer"
    UNCATEGORIZED = "uncategorized"


# ── Payment method prefixes to STRIP before classification ──────────
# Indian bank statements prefix every transaction with the method.
# "UPI/salary/HDFC" should match SALARY, not TRANSFER.
PAYMENT_METHOD_NOISE = [
    r'\b(upi|neft|rtgs|imps|nach|ecs|ach)\b[-/\\: ]*',
    r'\b(mob\s*trf|online\s*trf|net\s*banking|mobile\s*banking)\b[-/\\: ]*',
    r'\b(cr|dr)\b[-/\\: ]*',
    r'\b(inb|mob|atm|pos|ecom)\b[-/\\: ]*',
    r'\bref\s*(no|number)?[:\s]*\w+',
    r'\b\d{12,18}\b',                     # long reference numbers
    r'[/-]\d{6,}',                         # date/ref suffixes like /202403 or -987654
]
_NOISE_RE = re.compile('|'.join(PAYMENT_METHOD_NOISE), re.IGNORECASE)


def _clean_description(desc: str) -> str:
    """Strip payment-method noise so core intent keywords surface."""
    cleaned = _NOISE_RE.sub(' ', desc.lower().strip())
    return re.sub(r'\s+', ' ', cleaned).strip()


class TransactionClassifier:
    """Rule-based transaction classifier using keyword matching"""

    # ── Classification rules ────────────────────────────────────────
    # priority: higher = checked first.  is_credit: True/False/None
    CLASSIFICATION_RULES = {
        TransactionCategory.SALARY: {
            'keywords': [
                # Direct salary indicators
                'salary', 'sal cr', 'sal credit', 'payroll', 'wages',
                'monthly salary', 'salary account', 'emp sal', 'employee salary',
                'net salary', 'gross salary', 'sal transfer', 'sal trf',
                'company salary', 'monthly pay', 'salary credited',
                # Common Indian employer narration patterns
                'sal for', 'sal-', 'payroll credit', 'pay slip',
                'stipend', 'honorarium', 'pension cr', 'pension credit',
                'gratuity', 'arrear', 'arrears',
            ],
            'is_credit': True,
            'priority': 10
        },

        TransactionCategory.DEDUCTION_80D: {
            'keywords': [
                'health insurance', 'medical insurance', 'mediclaim premium',
                'health premium', 'medi claim', 'mediclaim',
                'preventive health checkup', 'health checkup', 'medical checkup',
                'health policy premium', 'family health insurance',
                'senior citizen health insurance', 'star health', 'niva bupa',
                'care health', 'max bupa', 'hdfc ergo health',
            ],
            'is_credit': False,
            'priority': 11
        },

        TransactionCategory.DEDUCTION_80C: {
            'keywords': [
                'ppf', 'public provident fund', 'epf', 'employees provident fund',
                'pf contribution', 'provident fund', 'vpf',
                'life insurance premium', 'lic premium', 'lic of india',
                'insurance premium', 'elss', 'equity linked savings',
                'tax saving fd', 'tax saver', 'nsc', 'national savings certificate',
                'sukanya samriddhi', 'senior citizen savings', 'scss',
                'tuition fees', 'education fees', 'school fees', 'college fees',
                'principal repayment', 'home loan principal', 'housing loan principal',
                'ulip premium', 'pension fund', 'nps', 'national pension',
                'sbi life', 'icici pru', 'hdfc life', 'max life',
                'bajaj allianz life', 'lic housing',
            ],
            'is_credit': False,
            'priority': 10
        },

        TransactionCategory.HOME_LOAN_INTEREST: {
            'keywords': [
                'home loan interest', 'housing loan interest', 'hl interest',
                'home loan emi', 'housing loan emi', 'hl emi', 'mortgage interest',
                'house loan interest', 'property loan interest',
                'mortgage emi', 'home loan', 'housing loan',
                'hdfc home loan', 'sbi home loan', 'lic housing loan',
                'pnb housing', 'bajaj housing',
            ],
            'is_credit': False,
            'priority': 9
        },

        TransactionCategory.INTEREST: {
            'keywords': [
                'interest', 'int cr', 'int credit', 'savings interest',
                'sb int', 'savings bank interest', 'interest credited',
                'int earned', 'bank interest', 'accrued interest',
                'fd interest', 'fixed deposit interest', 'rd interest',
                'recurring deposit interest', 'int on', 'credit interest',
                'int.cred', 'int pd', 'sweep interest',
            ],
            'is_credit': True,
            'priority': 9
        },

        TransactionCategory.DIVIDEND: {
            'keywords': [
                'dividend', 'div cr', 'dividend credit', 'stock dividend',
                'mutual fund dividend', 'mf dividend', 'equity dividend',
                'interim dividend', 'final dividend', 'div received',
                'div payout', 'idcw', 'income distribution',
            ],
            'is_credit': True,
            'priority': 9
        },

        TransactionCategory.RENTAL_INCOME: {
            'keywords': [
                'rent received', 'rental income', 'house rent', 'rent cr',
                'property rent', 'monthly rent', 'rental payment received',
                'tenant payment', 'lease payment', 'rent from', 'rent deposit',
                'rent for', 'hse rent',
            ],
            'is_credit': True,
            'priority': 9
        },

        TransactionCategory.CAPITAL_GAINS: {
            'keywords': [
                'capital gains', 'stock sale', 'equity sale', 'share sale',
                'mutual fund redemption', 'mf redemption', 'units redemption',
                'stock profit', 'trading profit', 'investment sale',
                'zerodha', 'groww', 'upstox', 'kite', 'angel broking',
                'motilal oswal', 'icici direct', 'hdfc securities',
                'sbi securities', 'kotak securities', 'share transfer',
                'cdsl', 'nsdl', 'depository', 'demat',
                'redemption', 'maturity proceeds', 'mf proceeds',
            ],
            'is_credit': True,
            'priority': 8
        },

        TransactionCategory.BUSINESS_INCOME: {
            'keywords': [
                'business income', 'professional fees', 'consulting fees',
                'freelance', 'freelancing', 'contract payment', 'client payment',
                'invoice payment', 'service charges received', 'commission received',
                'consultancy', 'professional charges', 'consulting income',
                'project payment', 'milestone payment', 'retainer',
            ],
            'is_credit': True,
            'priority': 8
        },

        TransactionCategory.DONATION: {
            'keywords': [
                'donation', 'charitable', 'charity', 'ngo contribution',
                'trust donation', 'temple donation', 'religious donation',
                'pm cares', 'prime minister relief fund', 'cm relief fund',
                'relief fund', '80g donation', 'section 80g',
                'gurudwara', 'church donation', 'mosque donation',
            ],
            'is_credit': False,
            'priority': 8
        },

        TransactionCategory.EXPENSE: {
            'keywords': [
                # Bills & utilities
                'electricity bill', 'water bill', 'gas bill', 'utility',
                'broadband bill', 'internet bill', 'wifi bill',
                'mobile recharge', 'dth recharge', 'phone bill',
                'bill payment', 'billdesk', 'bbps',
                # Credit card & EMI
                'credit card payment', 'cc payment', 'credit card bill',
                'emi', 'loan emi', 'auto debit', 'si debit',
                # Shopping & retail
                'purchase', 'shopping', 'grocery', 'grofers', 'bigbasket',
                'dmart', 'reliance retail', 'more retail',
                'pos purchase', 'pos debit', 'swipe', 'ecom purchase',
                'online shopping', 'amazon', 'flipkart', 'myntra', 'ajio',
                # Food & delivery
                'zomato', 'swiggy', 'food', 'restaurant', 'dining',
                'dominos', 'pizza hut', 'mcdonalds', 'starbucks', 'cafe',
                # Transport
                'uber', 'ola', 'rapido', 'metro', 'irctc',
                'petrol', 'diesel', 'fuel', 'hp petrol', 'indian oil',
                'bharat petroleum', 'shell', 'fuel station',
                'flight', 'makemytrip', 'goibibo', 'yatra',
                'hotel', 'oyo', 'airbnb', 'booking.com',
                'train', 'bus', 'travel', 'cab', 'taxi',
                # ATM & cash
                'atm withdrawal', 'cash withdrawal', 'atm wd', 'atm-wd',
                'atm cash', 'cash wdl', 'nfs wd', 'self wd',
                # Health
                'medical', 'pharmacy', 'hospital', 'doctor', 'apollo',
                'medplus', 'netmeds', '1mg', 'practo', 'diagnostic',
                # Entertainment & subscriptions
                'movie', 'pvr', 'inox', 'bookmyshow',
                'subscription', 'netflix', 'spotify', 'hotstar', 'prime video',
                'youtube premium', 'gym', 'cult fit',
                # Education
                'course', 'udemy', 'coursera', 'unacademy', 'byjus',
                # Insurance (non-80C/80D — e.g. car insurance)
                'vehicle insurance', 'car insurance', 'motor insurance',
                'bike insurance', 'general insurance',
                # Rent paid (outflow — NOT rental income)
                'rent paid', 'house rent paid', 'rent debit',
                # Misc
                'maintenance', 'society maintenance', 'maint charges',
                'service charge', 'annual fee', 'charges', 'penalty',
                'late fee', 'overdue charge', 'gst', 'tax payment',
                'advance tax', 'self assessment tax', 'tds',
            ],
            'is_credit': False,
            'priority': 6
        },

        TransactionCategory.TRANSFER: {
            'keywords': [
                # Only match EXPLICIT self/internal transfers
                'self transfer', 'own account', 'internal transfer',
                'self trf', 'own a/c', 'between own accounts',
                'sweep in', 'sweep out', 'od transfer',
                'fd placement', 'fd booking', 'fixed deposit booking',
                'rd installment', 'recurring deposit',
            ],
            'is_credit': None,
            'priority': 3    # Very low — last resort before uncategorized
        },
    }

    @staticmethod
    def classify(
        description: str,
        is_credit: bool,
        manually_labeled: bool = False,
        manual_category: Optional[str] = None
    ) -> Tuple[TransactionCategory, float]:
        """
        Classify a transaction based on description and type.

        1. Strip payment-method noise (UPI/NEFT/IMPS/RTGS prefixes, ref numbers)
        2. Match against rules sorted by priority (highest first)
        3. Fall back to amount-based heuristic for unmatched credits/debits
        """
        # Manual override
        if manually_labeled and manual_category:
            try:
                return TransactionCategory(manual_category), 1.0
            except ValueError:
                pass

        raw_desc = description.lower().strip()
        cleaned = _clean_description(description)

        # Sort rules by priority (highest first)
        sorted_rules = sorted(
            TransactionClassifier.CLASSIFICATION_RULES.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        )

        # ── Pass 1: match on CLEANED description (noise stripped) ───
        for category, rule in sorted_rules:
            if rule['is_credit'] is not None and rule['is_credit'] != is_credit:
                continue
            for keyword in rule['keywords']:
                if TransactionClassifier._keyword_match(cleaned, keyword):
                    return category, 0.9

        # ── Pass 2: match on RAW description (catches "UPI-SAL" etc.) ─
        for category, rule in sorted_rules:
            if rule['is_credit'] is not None and rule['is_credit'] != is_credit:
                continue
            for keyword in rule['keywords']:
                if TransactionClassifier._keyword_match(raw_desc, keyword):
                    return category, 0.85

        # ── Pass 3: heuristic for common uncategorised patterns ─────
        # Large round-number credits without any keyword → likely salary/income
        # Small debits → likely expense
        # Anything with UPI/NEFT/IMPS remaining → expense (debit) or uncategorized (credit)
        if not is_credit:
            # Debits that didn't match anything are general expenses
            return TransactionCategory.EXPENSE, 0.4

        # Credits that didn't match — could be refunds, misc income
        return TransactionCategory.UNCATEGORIZED, 0.0

    @staticmethod
    def _keyword_match(text: str, keyword: str) -> bool:
        """Check if keyword matches in text (substring or word-boundary)."""
        if keyword in text:
            return True
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text):
            return True
        return False

    @staticmethod
    def classify_bulk(
        transactions: list,
        respect_manual_labels: bool = True
    ) -> list:
        """Classify multiple transactions in bulk."""
        results = []
        for txn in transactions:
            manually_labeled = txn.get('manually_labeled', False) if respect_manual_labels else False
            manual_category = txn.get('manual_category') if respect_manual_labels else None
            category, confidence = TransactionClassifier.classify(
                description=txn['description'],
                is_credit=txn['is_credit'],
                manually_labeled=manually_labeled,
                manual_category=manual_category
            )
            results.append({
                'category': category.value,
                'confidence_score': confidence
            })
        return results

    @staticmethod
    def get_category_info(category: TransactionCategory) -> dict:
        """Get information about a category."""
        category_info = {
            TransactionCategory.SALARY: {
                'name': 'Salary Income',
                'tax_head': 'Income from Salary',
                'itr_section': 'Salaries',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.INTEREST: {
                'name': 'Interest Income',
                'tax_head': 'Income from Other Sources',
                'itr_section': 'Interest',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.DIVIDEND: {
                'name': 'Dividend Income',
                'tax_head': 'Income from Other Sources',
                'itr_section': 'Dividend',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.CAPITAL_GAINS: {
                'name': 'Capital Gains',
                'tax_head': 'Capital Gains',
                'itr_section': 'Capital Gains',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.RENTAL_INCOME: {
                'name': 'Rental Income',
                'tax_head': 'Income from House Property',
                'itr_section': 'House Property',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.BUSINESS_INCOME: {
                'name': 'Business/Professional Income',
                'tax_head': 'Profits and Gains from Business or Profession',
                'itr_section': 'Business/Profession',
                'is_taxable': True,
                'is_income': True
            },
            TransactionCategory.DEDUCTION_80C: {
                'name': 'Deduction under Section 80C',
                'tax_head': 'Deductions',
                'itr_section': 'Chapter VI-A (80C)',
                'is_taxable': False,
                'is_income': False,
                'max_deduction': 150000
            },
            TransactionCategory.DEDUCTION_80D: {
                'name': 'Health Insurance Premium (80D)',
                'tax_head': 'Deductions',
                'itr_section': 'Chapter VI-A (80D)',
                'is_taxable': False,
                'is_income': False,
                'max_deduction': 75000
            },
            TransactionCategory.HOME_LOAN_INTEREST: {
                'name': 'Home Loan Interest',
                'tax_head': 'Deductions',
                'itr_section': 'Section 24(b)',
                'is_taxable': False,
                'is_income': False,
                'max_deduction': 200000
            },
            TransactionCategory.DONATION: {
                'name': 'Donations (80G)',
                'tax_head': 'Deductions',
                'itr_section': 'Section 80G',
                'is_taxable': False,
                'is_income': False
            },
            TransactionCategory.TRANSFER: {
                'name': 'Fund Transfer',
                'tax_head': None,
                'itr_section': None,
                'is_taxable': False,
                'is_income': False
            },
            TransactionCategory.EXPENSE: {
                'name': 'General Expense',
                'tax_head': None,
                'itr_section': None,
                'is_taxable': False,
                'is_income': False
            },
            TransactionCategory.UNCATEGORIZED: {
                'name': 'Uncategorized',
                'tax_head': None,
                'itr_section': None,
                'is_taxable': False,
                'is_income': False
            }
        }
        return category_info.get(category, {
            'name': 'Unknown', 'tax_head': None,
            'itr_section': None, 'is_taxable': False, 'is_income': False
        })

    @staticmethod
    def get_tax_relevant_categories() -> list:
        """Get list of tax-relevant categories."""
        return [
            TransactionCategory.SALARY,
            TransactionCategory.INTEREST,
            TransactionCategory.DIVIDEND,
            TransactionCategory.CAPITAL_GAINS,
            TransactionCategory.RENTAL_INCOME,
            TransactionCategory.BUSINESS_INCOME,
            TransactionCategory.DEDUCTION_80C,
            TransactionCategory.DEDUCTION_80D,
            TransactionCategory.HOME_LOAN_INTEREST,
            TransactionCategory.DONATION
        ]

    @staticmethod
    def is_tax_relevant(category: TransactionCategory) -> bool:
        """Check if category is tax-relevant."""
        return category in TransactionClassifier.get_tax_relevant_categories()

    @staticmethod
    def add_custom_rule(
        category: TransactionCategory,
        keywords: list,
        is_credit: bool = None,
        priority: int = 5
    ):
        """Add a custom classification rule at runtime."""
        if category not in TransactionClassifier.CLASSIFICATION_RULES:
            TransactionClassifier.CLASSIFICATION_RULES[category] = {
                'keywords': [], 'is_credit': is_credit, 'priority': priority
            }
        existing = TransactionClassifier.CLASSIFICATION_RULES[category]['keywords']
        new_kw = [kw.lower() for kw in keywords if kw.lower() not in existing]
        existing.extend(new_kw)

    @staticmethod
    def get_statistics(transactions: list) -> dict:
        """Get classification statistics for a list of transactions."""
        total = len(transactions)
        if total == 0:
            return {}
        counts = {}
        for txn in transactions:
            cat = txn.get('category', TransactionCategory.UNCATEGORIZED.value)
            counts[cat] = counts.get(cat, 0) + 1
        return {
            cat: {'count': c, 'percentage': round((c / total) * 100, 2)}
            for cat, c in counts.items()
        }
