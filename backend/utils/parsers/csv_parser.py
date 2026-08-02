"""
CSV parser for bank statements
Handles all major Indian bank CSV export formats with multi-encoding support
and automatic metadata-row skipping.
"""
import csv
import io
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from .base_parser import BaseParser, ParsedTransaction, ParseResult, StatementMetadata

# Encodings to try in order
ENCODINGS = ['utf-8-sig', 'utf-8', 'latin-1', 'windows-1252', 'cp1252', 'iso-8859-1']


class CSVParser(BaseParser):
    """Parser for CSV bank statements"""

    # Minimum number of header keywords that must be present to accept a row as the header
    MIN_HEADER_MATCHES = 2

    def parse(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        """
        Parse CSV bank statement.
        Tries multiple encodings and automatically skips bank-specific metadata rows.
        """
        content, encoding = self._read_file(file_path)
        if content is None:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message="Could not decode file with any supported encoding"
            )

        # Find the actual header row (skip bank metadata rows at top)
        lines = content.splitlines()
        header_row_idx = self._find_header_row(lines)

        if header_row_idx is None:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message="Could not find a valid header row in CSV file"
            )

        # Extract metadata from rows before the header (account info, bank name, etc.)
        self._extract_metadata_from_preamble(lines[:header_row_idx])

        # Re-parse from the header row onwards
        data_content = "\n".join(lines[header_row_idx:])

        try:
            dialect = csv.Sniffer().sniff(data_content[:2048])
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(io.StringIO(data_content), dialect=dialect)

        if not reader.fieldnames:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message="No headers found in CSV file"
            )

        headers = list(reader.fieldnames)
        column_map = self.detect_columns(headers)

        if 'date' not in column_map:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message=f"Could not detect date column. Available columns: {', '.join(headers)}"
            )

        if 'description' not in column_map:
            # Some banks don't have a narration column; use the first non-date text column
            text_cols = [h for h in headers if h not in column_map.values()]
            if text_cols:
                column_map['description'] = text_cols[0]
            else:
                return ParseResult(
                    transactions=[],
                    metadata=self.metadata,
                    success=False,
                    error_message=f"Could not detect description column. Available columns: {', '.join(headers)}"
                )

        # Check for Dr/Cr indicator column (some banks use a single amount + indicator)
        dr_cr_col = self._find_dr_cr_column(headers, column_map)

        transactions = []
        warnings = []

        for row_num, row in enumerate(reader, start=header_row_idx + 2):
            try:
                transaction = self._parse_row(row, column_map, dr_cr_col)
                if transaction:
                    transactions.append(transaction)
            except Exception as e:
                warnings.append(f"Row {row_num}: {str(e)}")

        if not transactions:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message="No valid transactions found",
                warnings=warnings
            )

        # Derive metadata from transactions
        transactions.sort(key=lambda x: x.date)
        self.metadata.statement_period_start = transactions[0].date
        self.metadata.statement_period_end = transactions[-1].date
        if transactions[0].balance:
            self.metadata.closing_balance = transactions[-1].balance

        is_valid, val_warnings = self.validate_statement(transactions, self.metadata)
        warnings.extend(val_warnings)

        return ParseResult(
            transactions=transactions,
            metadata=self.metadata,
            success=is_valid,
            error_message=None if is_valid else "Validation failed",
            warnings=warnings
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _read_file(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Try multiple encodings; return (content, encoding) or (None, None)."""
        for enc in ENCODINGS:
            try:
                with open(file_path, 'r', encoding=enc, errors='strict') as f:
                    return f.read(), enc
            except (UnicodeDecodeError, LookupError):
                continue
        return None, None

    def _find_header_row(self, lines: List[str]) -> Optional[int]:
        """
        Scan lines to find the first row that looks like a transaction header.
        Returns the 0-based index of the header row.
        """
        header_keywords = ['date', 'narration', 'particulars', 'description',
                           'debit', 'credit', 'withdrawal', 'deposit',
                           'balance', 'amount', 'transaction', 'dr', 'cr']

        for idx, line in enumerate(lines):
            lower_line = line.lower()
            matches = sum(1 for kw in header_keywords if kw in lower_line)
            if matches >= self.MIN_HEADER_MATCHES:
                return idx

        return None

    def _find_dr_cr_column(self, headers: List[str], column_map: Dict) -> Optional[str]:
        """Detect a Dr/Cr indicator column used by some banks (e.g. 'Dr/Cr', 'Type')."""
        used_cols = set(column_map.values())
        for h in headers:
            if h in used_cols:
                continue
            hl = h.lower().strip()
            if hl in ('dr/cr', 'cr/dr', 'type', 'txn type', 'transaction type', 'dr / cr'):
                return h
        return None

    def _extract_metadata_from_preamble(self, preamble_lines: List[str]):
        """Extract bank name and account number from rows above the header."""
        text = "\n".join(preamble_lines)
        if not self.metadata.bank_name:
            self.metadata.bank_name = self.extract_bank_name(text)
        if not self.metadata.account_number:
            self.metadata.account_number = self.extract_account_number(text)

    def _parse_row(
        self,
        row: Dict[str, str],
        column_map: Dict[str, str],
        dr_cr_col: Optional[str] = None
    ) -> Optional[ParsedTransaction]:
        """Parse a single CSV row into a transaction."""
        # ---- date ----
        date_str = row.get(column_map['date'], '').strip()
        if not date_str:
            return None

        date = self.parse_date(date_str)
        if not date:
            return None  # skip unparseable dates silently

        # ---- description ----
        description = row.get(column_map['description'], '').strip()
        if not description:
            description = "Unknown Transaction"

        # ---- amounts ----
        debit = 0.0
        credit = 0.0
        balance = 0.0

        if 'debit' in column_map:
            debit = self.parse_amount(row.get(column_map['debit'], ''))
        if 'credit' in column_map:
            credit = self.parse_amount(row.get(column_map['credit'], ''))

        # Single amount column handling
        if 'amount' in column_map and not debit and not credit:
            amount = self.parse_amount(row.get(column_map['amount'], ''))
            if amount:
                if dr_cr_col:
                    indicator = row.get(dr_cr_col, '').strip().lower()
                    if any(d in indicator for d in ['dr', 'debit', 'withdrawal', 'w']):
                        debit = amount
                    elif any(c in indicator for c in ['cr', 'credit', 'deposit', 'd']):
                        credit = amount
                    else:
                        # Fallback to description sniffing
                        desc_lower = description.lower()
                        if any(w in desc_lower for w in ['debit', 'withdrawal', ' dr ', 'payment']):
                            debit = amount
                        else:
                            credit = amount
                else:
                    desc_lower = description.lower()
                    raw = row.get(column_map['amount'], '').strip()
                    # Negative values → debit; positive → credit
                    raw_clean = raw.replace(',', '').replace('₹', '').strip()
                    try:
                        signed = float(raw_clean)
                        if signed < 0:
                            debit = abs(signed)
                        elif signed > 0:
                            credit = signed
                        else:
                            return None
                    except ValueError:
                        if any(w in desc_lower for w in ['debit', 'withdrawal', ' dr ']):
                            debit = amount
                        else:
                            credit = amount

        if 'balance' in column_map:
            balance = self.parse_amount(row.get(column_map['balance'], ''))

        # Skip rows with no financial activity
        if debit == 0 and credit == 0:
            return None

        return ParsedTransaction(
            date=date,
            description=description,
            debit=debit,
            credit=credit,
            balance=balance
        )
