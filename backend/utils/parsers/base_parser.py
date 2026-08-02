"""
Base parser class for bank statement parsing
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
import re

@dataclass
class ParsedTransaction:
    """Canonical transaction schema"""
    date: datetime
    description: str
    debit: float
    credit: float
    balance: float
    
    def __post_init__(self):
        """Validate transaction data"""
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Debit and credit amounts cannot be negative")

@dataclass
class StatementMetadata:
    """Statement metadata extracted during parsing"""
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    statement_period_start: Optional[datetime] = None
    statement_period_end: Optional[datetime] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None

@dataclass
class ParseResult:
    """Result of parsing operation"""
    transactions: List[ParsedTransaction]
    metadata: StatementMetadata
    success: bool
    error_message: Optional[str] = None
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class BaseParser(ABC):
    """Base class for all statement parsers"""
    
    # Common column name patterns for auto-detection
    # Ordered from most-specific to least-specific to avoid false matches
    DATE_PATTERNS = [
        r'^txn[\s_]?date$', r'^tran[\s_]?date$', r'^transaction[\s_]?date$',
        r'^posting[\s_]?date$', r'^voucher[\s_]?date$', r'^chq[\s_]?date$',
        r'^value[\s_]?date$',  # fallback value date
        r'txn.*date', r'tran.*date', r'transaction.*date',
        r'^date$', r'^dt$', r'^dated$', r'date',
    ]
    
    DESCRIPTION_PATTERNS = [
        r'^narration$', r'^particulars$', r'^transaction[\s_]?remarks$',
        r'^transaction[\s_]?details$', r'^description$', r'^details$',
        r'^remarks$', r'^chq[\s_]?/?ref[\s_]?no\.?$',
        r'narration', r'particulars', r'description', r'remarks',
        r'transaction.*detail', r'transaction.*remark',
    ]
    
    DEBIT_PATTERNS = [
        r'^debit[\s_]?amount$', r'^withdrawal[\s_]?amt\.?(\s*\(.*\))?$',
        r'^dr[\s_]?amount$', r'^dr$', r'^debit$', r'^withdrawal$',
        r'^paid[\s_]?out$', r'^amount[\s_]?debit$',
        r'debit.*amount', r'withdrawal.*amt', r'dr.*amt',
        r'debit', r'withdrawal',
    ]
    
    CREDIT_PATTERNS = [
        r'^credit[\s_]?amount$', r'^deposit[\s_]?amt\.?(\s*\(.*\))?$',
        r'^cr[\s_]?amount$', r'^cr$', r'^credit$', r'^deposit$',
        r'^received$', r'^amount[\s_]?credit$',
        r'credit.*amount', r'deposit.*amt', r'cr.*amt',
        r'credit', r'deposit',
    ]
    
    BALANCE_PATTERNS = [
        r'^closing[\s_]?balance$', r'^running[\s_]?balance$',
        r'^available[\s_]?balance$', r'^bal$', r'^balance$',
        r'closing.*balance', r'running.*balance', r'balance',
    ]
    
    AMOUNT_PATTERNS = [
        r'^amount$', r'^transaction[\s_]?amount$', r'^txn[\s_]?amount$',
        r'transaction.*amount', r'txn.*amount', r'^amount$',
    ]
    
    def __init__(self):
        self.metadata = StatementMetadata()
    
    @abstractmethod
    def parse(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        """Parse the statement file"""
        pass
    
    def detect_column(self, headers: List[str], patterns: List[str]) -> Optional[str]:
        """
        Detect column name from headers using pattern matching.
        Patterns are tried in order; first match wins.
        
        Args:
            headers: List of column headers
            patterns: List of regex patterns to match
        
        Returns:
            Matched column name or None
        """
        headers_lower = [h.lower().strip() for h in headers]
        
        for pattern in patterns:
            pattern_compiled = re.compile(pattern, re.IGNORECASE)
            for i, header in enumerate(headers_lower):
                if pattern_compiled.search(header):
                    return headers[i]  # Return original case
        
        return None
    
    def detect_columns(self, headers: List[str]) -> Dict[str, str]:
        """
        Auto-detect all required columns
        
        Args:
            headers: List of column headers
        
        Returns:
            Dictionary mapping canonical names to actual column names
        """
        column_map = {}
        
        # Detect each column type
        date_col = self.detect_column(headers, self.DATE_PATTERNS)
        desc_col = self.detect_column(headers, self.DESCRIPTION_PATTERNS)
        debit_col = self.detect_column(headers, self.DEBIT_PATTERNS)
        credit_col = self.detect_column(headers, self.CREDIT_PATTERNS)
        balance_col = self.detect_column(headers, self.BALANCE_PATTERNS)
        amount_col = self.detect_column(headers, self.AMOUNT_PATTERNS)
        
        if date_col:
            column_map['date'] = date_col
        if desc_col:
            column_map['description'] = desc_col
        if debit_col:
            column_map['debit'] = debit_col
        if credit_col:
            column_map['credit'] = credit_col
        if balance_col:
            column_map['balance'] = balance_col
        if amount_col and not debit_col and not credit_col:
            column_map['amount'] = amount_col
        
        return column_map
    
    def parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string with multiple format support
        
        Args:
            date_str: Date string in various formats
        
        Returns:
            Parsed datetime object or None
        """
        if not date_str or str(date_str).strip() == '':
            return None
        
        date_str = str(date_str).strip()

        # If the cell contains multiple newline-separated dates (e.g. HDFC PDF),
        # take only the first non-empty line.
        if '\n' in date_str:
            for part in date_str.split('\n'):
                part = part.strip()
                if part:
                    date_str = part
                    break
        
        # Common Indian date formats
        date_formats = [
            '%d/%m/%Y',      # 01/12/2024
            '%d-%m-%Y',      # 01-12-2024
            '%d.%m.%Y',      # 01.12.2024
            '%Y-%m-%d',      # 2024-12-01 (ISO)
            '%d %b %Y',      # 01 Dec 2024
            '%d %b, %Y',    # 01 Dec, 2024 (Kotak format)
            '%d %B %Y',      # 01 December 2024
            '%d %B, %Y',    # 01 December, 2024
            '%d-%b-%Y',      # 01-Dec-2024
            '%d/%m/%y',      # 01/12/24
            '%d-%m-%y',      # 01-12-24
            '%b %d, %Y',     # Dec 01, 2024
            '%B %d, %Y',     # December 01, 2024
            '%d %b %y',      # 01 Dec 24
            '%d-%b-%y',      # 01-Dec-24
            '%m/%d/%Y',      # 12/01/2024 (US format fallback)
            '%Y/%m/%d',      # 2024/12/01
            '%d/%b/%Y',      # 01/Dec/2024
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Handle partial dates like "01 Feb" or "1 Feb" (no year) — infer year
        # Try formats without year, then append current/previous year
        partial_formats = ['%d %b', '%d %B', '%d-%b', '%d/%b']
        from datetime import date as _date
        current_year = _date.today().year
        for fmt in partial_formats:
            for year_offset in (0, -1, 1):
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    return parsed.replace(year=current_year + year_offset)
                except ValueError:
                    continue

        
        return None
    
    def parse_amount(self, amount_str: str) -> float:
        """
        Parse amount string to float
        
        Args:
            amount_str: Amount string (may include currency symbols, commas)
        
        Returns:
            Parsed float amount
        """
        if not amount_str or str(amount_str).strip() in ('', 'nan', 'None', '-', 'N/A', 'NA'):
            return 0.0
        
        amount_str = str(amount_str).strip()
        
        # Remove currency symbols, spaces, and Indian-style commas
        amount_str = re.sub(r'[₹$£€\s]', '', amount_str)
        # Remove commas used as thousand separators (handles Indian format like 1,23,456.78)
        amount_str = amount_str.replace(',', '')
        
        # Handle parentheses for negative amounts e.g. (1234.56)
        if amount_str.startswith('(') and amount_str.endswith(')'):
            amount_str = '-' + amount_str[1:-1]
        
        # Handle Dr/Cr suffix e.g. "1234.56 Dr" or "1234.56Cr"
        lower = amount_str.lower()
        if lower.endswith('dr'):
            amount_str = '-' + amount_str[:-2].strip()
        elif lower.endswith('cr'):
            amount_str = amount_str[:-2].strip()
        
        try:
            return abs(float(amount_str))  # Always return positive; caller decides sign
        except ValueError:
            return 0.0
    
    def validate_statement(
        self,
        transactions: List[ParsedTransaction],
        metadata: StatementMetadata
    ) -> Tuple[bool, List[str]]:
        """
        Validate parsed statement.
        Balance continuity issues are returned as warnings only — real bank statements
        often have rounding differences, multi-day postings, or missing balance columns.
        
        Args:
            transactions: List of parsed transactions
            metadata: Statement metadata
        
        Returns:
            Tuple of (is_valid, list of warning messages)
        """
        warnings = []
        
        # Check if transactions exist
        if not transactions:
            return False, ["No transactions found in statement"]
        
        # Check for obviously out-of-order dates (as a warning only)
        out_of_order = 0
        for i in range(1, len(transactions)):
            if transactions[i].date < transactions[i-1].date:
                out_of_order += 1
        if out_of_order > 0:
            warnings.append(f"{out_of_order} transaction(s) appear out of chronological order — statement may span multiple pages")
        
        # Balance continuity is informational only
        if metadata.closing_balance is not None and transactions:
            last_balance = transactions[-1].balance
            if last_balance and abs(last_balance - metadata.closing_balance) > 1.0:
                warnings.append(
                    f"Closing balance mismatch: statement says {metadata.closing_balance:.2f}, "
                    f"last transaction balance is {last_balance:.2f}"
                )
        
        return True, warnings
    
    def extract_account_number(self, text: str) -> Optional[str]:
        """
        Extract account number from text
        
        Args:
            text: Text containing account number
        
        Returns:
            Extracted account number or None
        """
        # Common patterns for account numbers
        patterns = [
            r'A/c\s*(?:No|Number)?[:\s]*(\d{9,18})',
            r'Account\s*(?:No|Number)?[:\s]*(\d{9,18})',
            r'Acct\s*(?:No|Number)?[:\s]*(\d{9,18})',
        ]
        
        text_lower = text.lower()
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def extract_bank_name(self, text: str) -> Optional[str]:
        """
        Extract bank name from text
        
        Args:
            text: Text containing bank name
        
        Returns:
            Extracted bank name or None
        """
        # Common Indian banks
        banks = [
            'State Bank of India', 'SBI',
            'HDFC Bank', 'HDFC',
            'ICICI Bank', 'ICICI',
            'Axis Bank', 'Axis',
            'Kotak Mahindra Bank', 'Kotak',
            'Punjab National Bank', 'PNB',
            'Bank of Baroda', 'BOB',
            'Canara Bank',
            'Union Bank of India',
            'Bank of India', 'BOI',
            'Indian Bank',
            'Central Bank of India',
            'Indian Overseas Bank', 'IOB',
            'UCO Bank',
            'Bank of Maharashtra',
        ]
        
        text_lower = text.lower()
        
        for bank in banks:
            if bank.lower() in text_lower:
                return bank
        
        return None
