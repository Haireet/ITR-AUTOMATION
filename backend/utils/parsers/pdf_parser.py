"""
PDF parser for bank statements.
Uses pdfplumber (preferred) for table/text extraction, with PyPDF2 as final fallback.
Strategies tried in order per page:
  1. pdfplumber table extraction (default settings)
  2. pdfplumber table extraction (text-based strategy)
  3. pdfplumber spatial word-grouping (column reconstruction)
  4. pdfplumber raw text + regex line parsing
  5. PyPDF2 raw text + regex line parsing
"""
import re
from typing import List, Dict, Optional, Tuple

from .base_parser import BaseParser, ParsedTransaction, ParseResult, StatementMetadata


class PDFParser(BaseParser):
    """Parser for PDF bank statements"""

    def parse(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        """Parse PDF bank statement."""
        try:
            try:
                import pdfplumber
                result = self._parse_with_pdfplumber(file_path, password)
                # If pdfplumber found transactions or hit a password error, return immediately.
                # Otherwise fall through to PyPDF2 (handles garbled-font PDFs like Kotak).
                if result.success or result.error_message == "PDF_PASSWORD_REQUIRED":
                    return result
            except ImportError:
                pass

            return self._parse_with_pypdf2(file_path, password)

        except Exception as e:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message=f"Failed to parse PDF: {str(e)}"
            )

    # ------------------------------------------------------------------ #
    #  pdfplumber — main implementation                                    #
    # ------------------------------------------------------------------ #

    def _parse_with_pdfplumber(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        import pdfplumber
        from pdfminer.pdfdocument import PDFPasswordIncorrect, PDFEncryptionError

        all_transactions: List[ParsedTransaction] = []
        warnings: List[str] = []

        try:
            open_kwargs = {}
            if password:
                open_kwargs["password"] = password
            pdf = pdfplumber.open(file_path, **open_kwargs)
        except (PDFPasswordIncorrect, PDFEncryptionError):
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message="PDF_PASSWORD_REQUIRED"
            )
        except Exception as e:
            err_msg = str(e).lower()
            if "password" in err_msg or "encrypted" in err_msg or "decrypt" in err_msg:
                return ParseResult(
                    transactions=[],
                    metadata=self.metadata,
                    success=False,
                    error_message="PDF_PASSWORD_REQUIRED"
                )
            raise

        with pdf:
            # Metadata from first two pages
            header_text = "".join(p.extract_text() or "" for p in pdf.pages[:2])
            self._extract_text_metadata(header_text)

            for page_num, page in enumerate(pdf.pages, start=1):
                page_txns: List[ParsedTransaction] = []

                # ── Strategy 1: default table extraction ──
                try:
                    for table in (page.extract_tables() or []):
                        txns, warns = self._parse_table(table, page_num)
                        page_txns.extend(txns)
                        warnings.extend(warns)
                except Exception as e:
                    warnings.append(f"Page {page_num} table extraction failed: {e}")

                # ── Strategy 2: text-based table detection (no lines needed) ──
                if not page_txns:
                    try:
                        text_tables = page.extract_tables(table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 5,
                            "intersection_tolerance": 5,
                        }) or []
                        for table in text_tables:
                            txns, warns = self._parse_table(table, page_num)
                            page_txns.extend(txns)
                            warnings.extend(warns)
                    except Exception:
                        pass

                # ── Strategy 3: spatial word grouping ──
                if not page_txns:
                    try:
                        txns, warns = self._parse_words_spatial(page, page_num)
                        page_txns.extend(txns)
                        warnings.extend(warns)
                    except Exception as e:
                        warnings.append(f"Page {page_num} spatial parse failed: {e}")

                # ── Strategy 4: raw text + regex ──
                if not page_txns:
                    text = page.extract_text() or ""
                    if text.strip():
                        txns, warns = self._parse_text_lines(text, page_num)
                        page_txns.extend(txns)
                        warnings.extend(warns)

                all_transactions.extend(page_txns)

        if not all_transactions:
            return ParseResult(
                transactions=[],
                metadata=self.metadata,
                success=False,
                error_message=(
                    "No transactions could be extracted from PDF. "
                    "This may be a scanned/image-based PDF. "
                    "Please download a text-based PDF or CSV export from your bank's net banking portal."
                ),
                warnings=warnings
            )

        all_transactions.sort(key=lambda x: x.date)
        self.metadata.statement_period_start = all_transactions[0].date
        self.metadata.statement_period_end = all_transactions[-1].date
        if all_transactions[-1].balance:
            self.metadata.closing_balance = all_transactions[-1].balance

        _, val_warnings = self.validate_statement(all_transactions, self.metadata)
        warnings.extend(val_warnings)

        return ParseResult(
            transactions=all_transactions,
            metadata=self.metadata,
            success=True,
            warnings=warnings
        )

    # ── Table parsing ──────────────────────────────────────────────────

    def _parse_table(self, table: List[List], page_num: int) -> Tuple[List[ParsedTransaction], List[str]]:
        transactions, warnings = [], []
        if not table or len(table) < 2:
            return transactions, warnings

        header_row_idx = None
        for i, row in enumerate(table[:10]):
            if row and self._is_header_row(row):
                header_row_idx = i
                break

        if header_row_idx is None:
            return transactions, warnings

        headers = [str(cell).strip() if cell else f"__col_{j}__"
                   for j, cell in enumerate(table[header_row_idx])]
        column_map = self.detect_columns(headers)

        if 'date' not in column_map:
            return transactions, warnings

        if 'description' not in column_map:
            used = set(column_map.values())
            for h in headers:
                if h not in used and not h.startswith('__col_'):
                    column_map['description'] = h
                    break

        for row_idx, row in enumerate(table[header_row_idx + 1:], start=1):
            if not row or all(not c for c in row):
                continue
            try:
                row_dict = {h: (str(row[i]).strip() if i < len(row) and row[i] else '')
                            for i, h in enumerate(headers)}
                txn = self._parse_row_dict(row_dict, column_map)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                warnings.append(f"PDF page {page_num}, table row {row_idx}: {e}")

        return transactions, warnings

    def _is_header_row(self, row: List) -> bool:
        if not row:
            return False
        values = [str(c).lower().strip() for c in row if c]
        keywords = ['date', 'narration', 'particulars', 'description',
                    'debit', 'credit', 'balance', 'amount', 'withdrawal',
                    'deposit', 'txn', 'tran']
        return sum(1 for kw in keywords if any(kw in v for v in values)) >= 2

    # ── Spatial word-grouping (handles PDFs without table borders) ──────

    def _parse_words_spatial(self, page, page_num: int) -> Tuple[List[ParsedTransaction], List[str]]:
        """Group words by Y-position to reconstruct rows, then detect columns."""
        transactions, warnings = [], []

        words = page.extract_words()
        if not words:
            return transactions, warnings

        # Group words into rows by y-position (tolerance 3pt)
        rows_by_y: Dict[int, List] = {}
        for w in words:
            y_key = round(w['top'] / 3) * 3  # snap to 3pt grid
            rows_by_y.setdefault(y_key, []).append(w)

        # Sort rows top-to-bottom; sort words in each row left-to-right
        sorted_rows = []
        for y_key in sorted(rows_by_y.keys()):
            row_words = sorted(rows_by_y[y_key], key=lambda w: w['x0'])
            sorted_rows.append(row_words)

        if not sorted_rows:
            return transactions, warnings

        # Find header row
        header_row_idx = None
        for i, row_words in enumerate(sorted_rows[:15]):
            texts = [w['text'].lower() for w in row_words]
            keywords = ['date', 'narration', 'particulars', 'description',
                        'debit', 'credit', 'balance', 'amount', 'dr', 'cr']
            if sum(1 for kw in keywords if any(kw in t for t in texts)) >= 2:
                header_row_idx = i
                break

        if header_row_idx is None:
            return transactions, warnings

        # Build header → x-range mapping
        header_words = sorted_rows[header_row_idx]
        col_ranges = self._build_column_ranges(header_words, page.width)
        if not col_ranges:
            return transactions, warnings

        headers = [col['text'] for col in col_ranges]
        column_map = self.detect_columns(headers)

        if 'date' not in column_map:
            return transactions, warnings

        if 'description' not in column_map:
            used = set(column_map.values())
            for h in headers:
                if h not in used:
                    column_map['description'] = h
                    break

        # Parse data rows
        for row_words in sorted_rows[header_row_idx + 1:]:
            try:
                row_dict = self._words_to_row_dict(row_words, col_ranges)
                txn = self._parse_row_dict(row_dict, column_map)
                if txn:
                    transactions.append(txn)
            except Exception as e:
                warnings.append(f"PDF page {page_num} spatial row: {e}")

        return transactions, warnings

    def _build_column_ranges(self, header_words: List, page_width: float) -> List[Dict]:
        """Build column x-ranges from header word positions."""
        cols = []
        sorted_words = sorted(header_words, key=lambda w: w['x0'])
        for i, w in enumerate(sorted_words):
            x_start = w['x0']
            x_end = sorted_words[i + 1]['x0'] if i + 1 < len(sorted_words) else page_width
            cols.append({'text': w['text'].strip(), 'x0': x_start, 'x1': x_end})
        return cols

    def _words_to_row_dict(self, row_words: List, col_ranges: List[Dict]) -> Dict[str, str]:
        """Assign words to columns by x-overlap, return a dict."""
        row_dict: Dict[str, str] = {col['text']: '' for col in col_ranges}
        for w in row_words:
            wx0, wx1 = w['x0'], w['x1']
            best_col = None
            best_overlap = 0.0
            for col in col_ranges:
                overlap = min(wx1, col['x1']) - max(wx0, col['x0'])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_col = col['text']
            if best_col is not None:
                row_dict[best_col] = (row_dict[best_col] + ' ' + w['text']).strip()
        return row_dict

    # ── Shared row-dict parser ─────────────────────────────────────────

    def _parse_row_dict(self, row: Dict[str, str], column_map: Dict[str, str]) -> Optional[ParsedTransaction]:
        date_str = row.get(column_map.get('date', ''), '').strip()
        if not date_str or date_str.lower() in ('date', 'nan', ''):
            return None
        date = self.parse_date(date_str)
        if not date:
            return None

        description = row.get(column_map.get('description', ''), '').strip() or "Unknown Transaction"

        debit  = self.parse_amount(row.get(column_map.get('debit', ''),  ''))
        credit = self.parse_amount(row.get(column_map.get('credit', ''), ''))

        if 'amount' in column_map and not debit and not credit:
            amount = self.parse_amount(row.get(column_map['amount'], ''))
            if amount:
                desc_lower = description.lower()
                if any(w in desc_lower for w in ['dr', 'debit', 'withdrawal']):
                    debit = amount
                else:
                    credit = amount

        balance = self.parse_amount(row.get(column_map.get('balance', ''), ''))

        if debit == 0 and credit == 0:
            return None

        return ParsedTransaction(date=date, description=description,
                                 debit=debit, credit=credit, balance=balance)

    # ── Text-line regex fallback ───────────────────────────────────────

    # Match: date  description  [amount1]  [amount2]  [amount3]
    # Amounts may optionally carry a +/- sign (e.g. Kotak bank statements).
    LINE_PATTERN = re.compile(
        r'^(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+\w{3},?\s+\d{2,4}|\d{2}\w{3}\d{4})'
        r'\s+'
        r'(.+?)\s+'
        r'([+-]?[\d,]+\.?\d{0,2})'
        r'(?:\s+([+-]?[\d,]+\.?\d{0,2}))?'
        r'(?:\s+([+-]?[\d,]+\.?\d{0,2}))?'
        r'\s*$'
    )

    @staticmethod
    def _merge_continuation_lines(text: str) -> str:
        """Merge continuation lines (lines not starting with a date) into the previous line."""
        date_start = re.compile(r'^\d{1,2}[\s./-]')
        merged, lines = [], text.splitlines()
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if date_start.match(stripped) or not merged:
                merged.append(stripped)
            else:
                merged[-1] = merged[-1] + stripped
        return '\n'.join(merged)

    def _parse_text_lines(self, text: str, page_num: int) -> Tuple[List[ParsedTransaction], List[str]]:
        """Regex-based transaction extraction from raw text lines."""
        transactions, warnings = [], []

        text = self._merge_continuation_lines(text)

        for line_num, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            m = self.LINE_PATTERN.match(line)
            if not m:
                continue
            try:
                date = self.parse_date(m.group(1))
                if not date:
                    continue
                description = m.group(2).strip()
                raw_groups = [g for g in m.groups()[2:] if g]
                amounts = [self.parse_amount(g) for g in raw_groups]

                if len(amounts) == 1:
                    continue  # can't determine Dr/Cr
                elif len(amounts) == 2:
                    # Use explicit +/- sign if present to decide debit vs credit
                    first_raw = raw_groups[0].strip()
                    if first_raw.startswith('-'):
                        debit, credit, balance = amounts[0], 0.0, amounts[1]
                    elif first_raw.startswith('+'):
                        debit, credit, balance = 0.0, amounts[0], amounts[1]
                    else:
                        desc_lower = description.lower()
                        if any(w in desc_lower for w in ['cr', 'deposit', 'received', 'credit']):
                            debit, credit, balance = 0.0, amounts[0], amounts[1]
                        else:
                            debit, credit, balance = amounts[0], 0.0, amounts[1]
                else:  # 3 amounts → debit, credit, balance
                    debit, credit, balance = amounts[0], amounts[1], amounts[2]

                if debit == 0 and credit == 0:
                    continue

                transactions.append(ParsedTransaction(
                    date=date, description=description,
                    debit=debit, credit=credit, balance=balance
                ))
            except Exception as e:
                warnings.append(f"PDF page {page_num}, line {line_num}: {e}")

        return transactions, warnings

    # ── PyPDF2 final fallback ──────────────────────────────────────────

    def _parse_with_pypdf2(self, file_path: str, password: Optional[str] = None) -> ParseResult:
        try:
            import PyPDF2
            all_text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    if password:
                        try:
                            reader.decrypt(password)
                        except Exception:
                            return ParseResult(
                                transactions=[], metadata=self.metadata, success=False,
                                error_message="PDF_PASSWORD_REQUIRED"
                            )
                    else:
                        return ParseResult(
                            transactions=[], metadata=self.metadata, success=False,
                            error_message="PDF_PASSWORD_REQUIRED"
                        )
                self._extract_text_metadata(
                    "".join(p.extract_text() or "" for p in reader.pages[:2])
                )
                for page in reader.pages:
                    all_text += (page.extract_text() or "") + "\n"

            transactions, warnings = self._parse_text_lines(all_text, 0)

            if not transactions:
                return ParseResult(
                    transactions=[], metadata=self.metadata, success=False,
                    error_message=(
                        "Could not extract transactions from PDF. "
                        "This appears to be a scanned/image PDF. "
                        "Please download a CSV or text-based PDF from your bank's net banking portal."
                    ),
                    warnings=warnings
                )

            transactions.sort(key=lambda x: x.date)
            return ParseResult(transactions=transactions, metadata=self.metadata,
                               success=True, warnings=warnings)
        except Exception as e:
            return ParseResult(transactions=[], metadata=self.metadata, success=False,
                               error_message=f"PDF parsing failed: {str(e)}")

    # ── Metadata ───────────────────────────────────────────────────────

    def _extract_text_metadata(self, text: str):
        if not self.metadata.bank_name:
            self.metadata.bank_name = self.extract_bank_name(text)
        if not self.metadata.account_number:
            self.metadata.account_number = self.extract_account_number(text)

        for pattern in [
            r'Statement\s+Period[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s+to\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
            r'From[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s+To[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
            r'Period[:\s]+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*[-–to]+\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})',
        ]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                s = self.parse_date(m.group(1))
                e = self.parse_date(m.group(2))
                if s: self.metadata.statement_period_start = s
                if e: self.metadata.statement_period_end = e
                break
                  