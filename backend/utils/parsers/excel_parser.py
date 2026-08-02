"""
Excel parser for bank statements.
Handles XLS/XLSX exports from all major Indian banks.
Uses pandas (handles both .xls and .xlsx) with openpyxl as a secondary path.
"""
import os
from typing import List, Dict, Optional
from datetime import datetime

from .base_parser import BaseParser, ParsedTransaction, ParseResult, StatementMetadata


class ExcelParser(BaseParser):
    """Parser for Excel bank statements (XLS, XLSX)"""

    def parse(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        """Parse Excel bank statement — tries pandas first (handles .xls + .xlsx),
        falls back to openpyxl for .xlsx."""
        ext = os.path.splitext(file_path)[1].lower()

        # ── Primary: pandas (handles both .xls via xlrd and .xlsx via openpyxl) ──
        try:
            import pandas as pd
            engine = 'xlrd' if ext == '.xls' else 'openpyxl'
            sheets: Dict = pd.read_excel(
                file_path, sheet_name=None, header=None, dtype=str, engine=engine
            )
            for sheet_name, df in sheets.items():
                result = self._parse_dataframe(df, str(sheet_name))
                if result.success or result.transactions:
                    return result
            # All sheets failed — return the last error with a helpful message
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message=self._best_error(sheets)
            )
        except ImportError:
            pass  # pandas not available — fall through to openpyxl
        except Exception as e:
            if ext == '.xls':
                return ParseResult(
                    transactions=[],
                    metadata=self.metadata,
                    success=False,
                    error_message=f"Failed to read .xls file: {str(e)}. Ensure xlrd is installed."
                )
            # For .xlsx fall through to openpyxl

        # ── Fallback: openpyxl (xlsx only) ──
        if ext != '.xls':
            return self._parse_with_openpyxl(file_path)

        return ParseResult(
            transactions=[],
            metadata=self.metadata,
            success=False,
            error_message="Failed to parse Excel file. Please ensure xlrd is installed for .xls files."
        )

    # ------------------------------------------------------------------ #
    #  pandas path                                                          #
    # ------------------------------------------------------------------ #

    def _parse_dataframe(self, df, sheet_name: str) -> ParseResult:
        """Parse a pandas DataFrame (one sheet) into transactions."""
        if df.empty:
            return ParseResult(transactions=[], metadata=self.metadata,
                               success=False, error_message=f"Sheet '{sheet_name}' is empty")

        # Stringify all cells for uniform processing
        df = df.fillna('').astype(str)

        # Find header row
        header_row_idx = self._find_header_row_df(df)
        if header_row_idx is None:
            # Dump first few headers for diagnosis
            first_row = list(df.iloc[0]) if len(df) > 0 else []
            return ParseResult(
                transactions=[], metadata=self.metadata, success=False,
                error_message=f"Sheet '{sheet_name}': no header row found. "
                              f"First row values: {first_row[:8]}"
            )

        # Extract metadata from preamble rows
        preamble_text = " ".join(
            df.iloc[:header_row_idx].values.flatten().tolist()
        )
        if not self.metadata.bank_name:
            self.metadata.bank_name = self.extract_bank_name(preamble_text)
        if not self.metadata.account_number:
            self.metadata.account_number = self.extract_account_number(preamble_text)

        # Extract statement year from preamble for partial dates like "01 Feb"
        import re as _re
        statement_year = None
        year_match = _re.search(r'\b(20\d{2})\b', preamble_text)
        if year_match:
            statement_year = int(year_match.group(1))

        # Build column map
        headers = list(df.iloc[header_row_idx])
        column_map = self.detect_columns(headers)

        if 'date' not in column_map:
            return ParseResult(
                transactions=[], metadata=self.metadata, success=False,
                error_message=f"Sheet '{sheet_name}': date column not found. "
                              f"Detected headers: {[h for h in headers if h.strip()]}"
            )

        # Fallback: use first non-mapped non-empty column as description
        if 'description' not in column_map:
            used = set(column_map.values())
            for h in headers:
                if h.strip() and h not in used:
                    column_map['description'] = h
                    break

        # Detect Dr/Cr indicator column
        dr_cr_col = self._find_dr_cr_col(headers, column_map)

        # Parse data rows
        transactions = []
        warnings = []
        data_df = df.iloc[header_row_idx + 1:].reset_index(drop=True)

        for idx, row in data_df.iterrows():
            row_dict = dict(zip(headers, row.values))
            try:
                txn = self._parse_row_dict(row_dict, column_map, dr_cr_col, statement_year)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                warnings.append(f"Sheet '{sheet_name}', row {idx + header_row_idx + 2}: {e}")

        if not transactions:
            return ParseResult(
                transactions=[], metadata=self.metadata, success=False,
                error_message=f"Sheet '{sheet_name}': no valid transactions found",
                warnings=warnings
            )

        transactions.sort(key=lambda x: x.date)
        self.metadata.statement_period_start = transactions[0].date
        self.metadata.statement_period_end = transactions[-1].date
        if transactions[-1].balance:
            self.metadata.closing_balance = transactions[-1].balance

        _, val_warnings = self.validate_statement(transactions, self.metadata)
        warnings.extend(val_warnings)

        return ParseResult(
            transactions=transactions, metadata=self.metadata,
            success=True, warnings=warnings
        )

    def _find_header_row_df(self, df) -> Optional[int]:
        """Find the header row in a pandas DataFrame (search all rows up to 50).
        Requires a date-like column to be present to avoid matching summary rows."""
        keywords = ['date', 'narration', 'particulars', 'description',
                    'debit', 'credit', 'balance', 'amount', 'withdrawal',
                    'deposit', 'dr', 'cr', 'txn', 'tran', 'value']
        # A real transaction header must have a date column
        date_keywords = ['date', 'txn', 'tran', 'value dt', 'posting']
        for idx in range(min(50, len(df))):
            row_vals = [str(v).lower().strip() for v in df.iloc[idx].values]
            matches = sum(1 for kw in keywords if any(kw in v for v in row_vals))
            has_date = any(any(dk in v for dk in date_keywords) for v in row_vals)
            if matches >= 2 and has_date:
                return idx
        return None

    def _find_dr_cr_col(self, headers: List[str], column_map: Dict) -> Optional[str]:
        """Detect Dr/Cr indicator column name."""
        used = set(column_map.values())
        for h in headers:
            if h in used:
                continue
            hl = h.lower().strip()
            if hl in ('dr/cr', 'cr/dr', 'type', 'txn type', 'transaction type',
                      'dr / cr', 'debit/credit'):
                return h
        return None

    def _parse_row_dict(
        self,
        row: Dict[str, str],
        column_map: Dict[str, str],
        dr_cr_col: Optional[str],
        statement_year: Optional[int] = None
    ) -> Optional[ParsedTransaction]:
        """Parse a row dict into a ParsedTransaction."""
        # Date
        date_str = str(row.get(column_map.get('date', ''), '')).strip()
        if not date_str or date_str in ('', 'nan', 'None'):
            return None
        date = self.parse_date(date_str)
        # Retry with statement year for partial dates like "01 Feb" or "1 February"
        if not date and statement_year:
            import re as _re
            if _re.match(r'^\d{1,2}\s+[A-Za-z]{3,}$', date_str):
                date = self.parse_date(f"{date_str} {statement_year}")
        if not date:
            return None

        # Description
        description = str(row.get(column_map.get('description', ''), '')).strip()
        if not description or description in ('nan', 'None'):
            description = "Unknown Transaction"

        # Amounts
        debit = self.parse_amount(str(row.get(column_map.get('debit', ''), '')))
        credit = self.parse_amount(str(row.get(column_map.get('credit', ''), '')))

        # Single amount column
        if 'amount' in column_map and not debit and not credit:
            raw = str(row.get(column_map['amount'], '')).strip()
            amount = self.parse_amount(raw)
            if amount:
                if dr_cr_col:
                    indicator = str(row.get(dr_cr_col, '')).strip().lower()
                    if any(d in indicator for d in ['dr', 'debit', 'withdrawal', 'w']):
                        debit = amount
                    else:
                        credit = amount
                else:
                    # Try to infer from sign in raw value
                    try:
                        signed = float(raw.replace(',', '').replace('₹', '').strip())
                        if signed < 0:
                            debit = abs(signed)
                        else:
                            credit = amount
                    except ValueError:
                        desc_lower = description.lower()
                        if any(w in desc_lower for w in ['dr', 'debit', 'withdrawal']):
                            debit = amount
                        else:
                            credit = amount

        balance = self.parse_amount(str(row.get(column_map.get('balance', ''), '')))

        if debit == 0 and credit == 0:
            return None

        return ParsedTransaction(
            date=date, description=description,
            debit=debit, credit=credit, balance=balance
        )

    def _best_error(self, sheets: Dict) -> str:
        """Build a helpful error message when all sheets fail."""
        names = list(sheets.keys())
        return (
            f"No valid transaction data found in any sheet ({', '.join(str(n) for n in names)}). "
            "Ensure the file has columns for Date, Description, and Debit/Credit amounts."
        )

    # ------------------------------------------------------------------ #
    #  openpyxl fallback (xlsx only)                                        #
    # ------------------------------------------------------------------ #

    def _parse_with_openpyxl(self, file_path: str) -> ParseResult:
        """Parse .xlsx using openpyxl directly."""
        try:
            import openpyxl
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            for sheet in workbook.worksheets:
                result = self._parse_openpyxl_sheet(sheet)
                if result.success or result.transactions:
                    return result
            return ParseResult(
                transactions=[], metadata=self.metadata, success=False,
                error_message="No transaction data found in any sheet"
            )
        except Exception as e:
            return ParseResult(
                transactions=[], metadata=self.metadata, success=False,
                error_message=f"Failed to parse Excel (openpyxl): {str(e)}"
            )

    def _parse_openpyxl_sheet(self, sheet) -> ParseResult:
        """Parse a single openpyxl worksheet."""
        rows = []
        for row in sheet.iter_rows():
            rows.append([
                str(cell.value).strip() if cell.value is not None else ''
                for cell in row
            ])

        if not rows:
            return ParseResult(transactions=[], metadata=self.metadata,
                               success=False, error_message="Empty sheet")

        import pandas as pd
        df = pd.DataFrame(rows).astype(str)
        return self._parse_dataframe(df, sheet.title)
