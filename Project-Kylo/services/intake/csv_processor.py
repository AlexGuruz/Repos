"""
CSV Processor Service
Parses CSV content and extracts petty cash transactions with deduplication
"""

import csv
import hashlib
import logging
import os
import json
import re
import uuid
from datetime import datetime
from services.common.config_loader import load_config
from typing import Dict, Iterator, List, Optional, Tuple

log = logging.getLogger(__name__)


class CSVProcessingError(Exception):
    """Raised when CSV processing fails"""
    pass


class PettyCashCSVProcessor:
    """Processes petty cash CSV data with comprehensive deduplication"""
    
    def __init__(
        self,
        csv_content: str,
        header_rows: int = 19,
        source_tab: Optional[str] = None,
        source_spreadsheet_id: Optional[str] = None,
    ):
        self.csv_content = csv_content
        self.seen_rows = set()  # Track seen rows within this file
        self.source_tab = (source_tab or "").strip().upper()  # Track which tab this CSV came from
        self.source_spreadsheet_id = (source_spreadsheet_id or "").strip()
        self.file_fingerprint = self._get_file_fingerprint()

        def _col_letter_to_index(value: Optional[str]) -> Optional[int]:
            if value is None:
                return None
            s = str(value).strip().upper()
            if not s:
                return None
            # Support 'A'..'Z' and 'AA'..'ZZ'
            if not re.fullmatch(r"[A-Z]+", s):
                return None
            n = 0
            for ch in s:
                n = n * 26 + (ord(ch) - ord("A") + 1)
            return n - 1  # 0-based

        # Load config: prefer unified YAML; then optional JSON (KYLO_CSV_CONFIG_PATH)
        self._config: Dict = {}
        self._yaml: Dict = {}
        cfg_path = os.environ.get("KYLO_CSV_CONFIG_PATH", os.path.join("config", "csv_processor_config.json"))
        try:
            try:
                self._yaml = load_config().data  # entire YAML for nested lookups
            except Exception:
                self._yaml = {}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f) or {}
        except Exception as e:
            log.warning("csv_processor: failed to load configs: %s", e)
            self._config = {}

        petty_cfg = self._config.get("petty_cash", {}) if isinstance(self._config, dict) else {}

        # Header rows: respect constructor value unless it's the default and config provides an override
        # YAML override takes precedence when provided
        yaml_header_rows = None
        yaml_start_row = None
        try:
            yaml_header_rows = int(((self._yaml.get("intake", {}) or {}).get("csv_processor", {}) or {}).get("header_rows"))
        except Exception:
            yaml_header_rows = None
        try:
            yaml_start_row = int(((self._yaml.get("intake", {}) or {}).get("csv_processor", {}) or {}).get("start_row"))
        except Exception:
            yaml_start_row = None
        cfg_header_rows = petty_cfg.get("header_rows") if isinstance(petty_cfg, dict) else None
        if cfg_header_rows is not None and header_rows == 19:
            try:
                self.header_rows = int(cfg_header_rows)
            except Exception:
                self.header_rows = header_rows
        elif yaml_header_rows is not None and header_rows == 19:
            self.header_rows = yaml_header_rows
        else:
            self.header_rows = header_rows

        # If config provides an explicit start_row (1-based), prefer skipping everything above it
        # for banner-heavy *sheet tabs* (e.g. PETTY CASH).
        #
        # IMPORTANT:
        # - Only apply this when source_tab is explicitly provided. This avoids surprising behavior
        #   for generic CSV inputs (unit tests, ad-hoc CSV files) where callers expect header_rows
        #   to be honored exactly.
        # - Never apply to structured tabs like BANK/TRANSACTIONS (header row at 1).
        if self.source_tab and self.source_tab not in ("BANK", "TRANSACTIONS"):
            if yaml_start_row is not None and int(yaml_start_row) > 1:
                self.header_rows = max(int(self.header_rows), int(yaml_start_row) - 1)

        # Date formats
        cfg_formats = []
        yaml_formats = []
        try:
            cfg_formats = (petty_cfg.get("columns", {}).get("date", {}) or {}).get("format") or []
        except Exception:
            cfg_formats = []
        try:
            yaml_formats = ((self._yaml.get("intake", {}) or {}).get("csv_processor", {}) or {}).get("date_formats") or []
        except Exception:
            yaml_formats = []
        default_formats = ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%m/%d/%y', '%m-%d-%y']
        # Merge keeping order and uniqueness; ensure hyphen and slash variants always present
        seen = set()
        merged: List[str] = []
        for fmt in list(yaml_formats) + list(cfg_formats) + default_formats:
            if fmt not in seen:
                seen.add(fmt)
                merged.append(fmt)
        self.date_formats = merged

        # Column mapping
        #
        # We support multiple intake tab shapes:
        # - TRANSACTIONS: DATE, COMPANY, SOURCE, AMOUNT, ... (header row 1)
        # - BANK: DATE, COMPANY, SOURCE, AMOUNT, ... (header row 1)
        # - PETTY CASH / other legacy tabs: often have banner/header blocks; use YAML intake.csv_processor.columns
        yaml_cols = (((self._yaml.get("intake", {}) or {}).get("csv_processor", {}) or {}).get("columns") or {})
        date_idx = _col_letter_to_index((yaml_cols or {}).get("date")) if isinstance(yaml_cols, dict) else None
        desc_idx = _col_letter_to_index((yaml_cols or {}).get("description")) if isinstance(yaml_cols, dict) else None
        amt_idx = _col_letter_to_index((yaml_cols or {}).get("amount")) if isinstance(yaml_cols, dict) else None
        company_idx = _col_letter_to_index((yaml_cols or {}).get("company_hint")) if isinstance(yaml_cols, dict) else None

        # Defaults (legacy-safe): Standard petty cash layout is often
        # A=initials, B=date, C=company, D=desc, E=amount, F=posted
        self.column_mapping = {
            "initials": 0,  # A
            "date": date_idx if date_idx is not None else 1,  # B
            "company": company_idx if company_idx is not None else 2,  # C
            "source": desc_idx if desc_idx is not None else 3,  # D
            "total": amt_idx if amt_idx is not None else 4,  # E
            "posted": 5,  # F (checkbox)
        }

        if self.source_tab in ("BANK", "TRANSACTIONS"):
            # Both BANK and TRANSACTIONS are "structured" tabs in the year workbooks:
            # A=date, B=company, C=description/source, D=amount, F=posted/processed checkbox, G=notes
            self.column_mapping.update(
                {
                    "initials": 0,  # not used; allow parser to ignore if no initials
                    "date": 0,
                    "company": 1,
                    "source": 2,
                    "total": 3,
                    "posted": 5,
                }
            )
            # Ensure we only skip the header row on these tabs unless user explicitly overrides.
            self.header_rows = min(int(self.header_rows or 1), 1)

        # Valid companies set, prefer YAML sheets.companies; else legacy JSONs
        self.valid_companies = self._load_valid_companies()
    
    def _get_file_fingerprint(self) -> str:
        """Generate SHA256 hash of CSV content"""
        # Backwards compatible: when we don't know the spreadsheet/tab, hash just content.
        # When we DO know the spreadsheet/tab, include them so different workbooks don't collide.
        if self.source_spreadsheet_id or self.source_tab:
            payload = f"{self.source_spreadsheet_id}|{self.source_tab}|{self.csv_content}"
        else:
            payload = self.csv_content
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    
    def parse_transactions(self) -> Iterator[Dict]:
        """Parse CSV and yield normalized transactions with row-level deduplication"""
        lines = self.csv_content.split('\n')

        # Dynamic header detection: if a header row exists, infer indices by header names
        dynamic_mapping = None
        # For BANK/TRANSACTIONS, also infer the "processed/posted" checkbox column by name.
        dynamic_posted_idx = None
        if self.header_rows > 0 and len(lines) >= self.header_rows:
            try:
                header_line = lines[self.header_rows - 1]
                header_row = next(csv.reader([header_line]))
                header_index = {str(h).strip().lower(): i for i, h in enumerate(header_row)}
                # Common expected header names
                date_idx = header_index.get('date')
                amount_idx = header_index.get('amount')
                company_idx = header_index.get('company')
                desc_idx = header_index.get('description')
                # Common processed column names seen in year workbooks
                for key in ("processed", "posted", "process", "done"):
                    if key in header_index:
                        dynamic_posted_idx = header_index.get(key)
                        break
                if all(idx is not None for idx in (date_idx, amount_idx, company_idx, desc_idx)):
                    dynamic_mapping = {
                        'initials': self.column_mapping.get('initials', 0),
                        'date': date_idx,
                        'company': company_idx,
                        'source': desc_idx,
                        'total': amount_idx,
                    }
            except Exception:
                dynamic_mapping = None
                dynamic_posted_idx = None

        data_lines = lines[self.header_rows:]
        
        log.info(f"Processing {len(data_lines)} data rows (skipping {self.header_rows} header rows)")
        
        for row_index, line in enumerate(data_lines, start=self.header_rows):
            if not line.strip():
                continue
            
            # Generate row fingerprint for deduplication
            row_fingerprint = self._generate_row_fingerprint(line, row_index)
            
            # Skip if we've seen this exact row before
            if row_fingerprint in self.seen_rows:
                log.debug(f"Skipping duplicate row {row_index}")
                continue
            
            self.seen_rows.add(row_fingerprint)
            
            # Parse row
            try:
                reader = csv.reader([line])
                row = next(reader)
                # Use dynamic header-derived mapping when available
                original_mapping = self.column_mapping
                if dynamic_mapping is not None:
                    # Adopt dynamic mapping from the header row when present.
                    # This is critical for TRANSACTIONS/BANK tabs, which are header-driven.
                    self.column_mapping.update({
                        'initials': dynamic_mapping.get('initials', self.column_mapping['initials']),
                        'date': dynamic_mapping.get('date', self.column_mapping['date']),
                        'company': dynamic_mapping.get('company', self.column_mapping['company']),
                        'source': dynamic_mapping.get('source', self.column_mapping['source']),
                        'total': dynamic_mapping.get('total', self.column_mapping['total']),
                        # posted stays where it is (typically F)
                    })
                # If we detected a processed/posted checkbox column, use it.
                if dynamic_posted_idx is not None:
                    try:
                        self.column_mapping['posted'] = int(dynamic_posted_idx)
                    except Exception:
                        pass
                transaction = self._parse_transaction_row(row, row_index)
                # Restore original mapping for next rows
                self.column_mapping = original_mapping
                if transaction:
                    yield transaction
                    
            except Exception as e:
                log.warning(f"Error parsing row {row_index}: {e}")
                continue
    
    def _generate_row_fingerprint(self, line: str, row_index: int) -> str:
        """Generate fingerprint for a specific row"""
        # Use just the line content for deduplication (same content = same fingerprint)
        payload = line.strip()
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def _parse_transaction_row(self, row: List[str], row_index: int) -> Optional[Dict]:
        """Parse individual transaction row"""
        try:
            # For BANK tab, handle different column structure:
            # Column A = Date, Column B = Company (may be empty or have JGD), Column C = Description, Column D = Amount
            if self.source_tab == "BANK":
                # Always extract company first (Column B) - may be empty or contain JGD
                company = self._extract_company(row) or "JGD"
                if company not in self.valid_companies:
                    company = "JGD"  # Default to JGD for BANK tab
                
                # Try to extract date from Column A (BANK tab format)
                date_from_a = self._parse_date_from_column(row, 0)  # Column A (index 0)
                
                # Extract description and amount (these should always be in Column C and D)
                source_description = self._extract_source(row)
                amount = self._parse_amount(row)
                
                # Validate required fields
                if not source_description:
                    # BANK tab can contain many blank/partial rows; avoid log spam.
                    return None
                if amount is None:
                    # BANK tab can contain many blank/partial rows; avoid log spam.
                    return None
                
                # If date parsing from Column A succeeded, use it
                if date_from_a:
                    posted_date = date_from_a
                else:
                    # Date parsing from Column A failed - try standard date column as fallback
                    posted_date = self._parse_date(row)
                    if not posted_date:
                        # Last resort: try to parse date from Column A with more lenient parsing
                        if len(row) > 0:
                            date_str = row[0].strip()
                            # Try common date formats with more flexibility
                            for fmt in ['%m/%d/%y', '%m/%d/%Y', '%m-%d-%y', '%m-%d-%Y', '%Y-%m-%d']:
                                try:
                                    parsed_date = datetime.strptime(date_str, fmt)
                                    posted_date = parsed_date.strftime('%Y-%m-%d')
                                    break
                                except ValueError:
                                    continue
                    
                    if not posted_date:
                        # Avoid log spam on malformed/blank rows.
                        return None
                
                # Generate transaction
                txn_uid = self._generate_txn_uid(company, row_index, posted_date, int(amount * 100), source_description)
                content_hash = self._generate_content_hash(company, posted_date, amount, source_description)
                business_hash = self._generate_business_hash(company, posted_date, amount, source_description)
                
                return {
                    "txn_uid": txn_uid,
                    "company_id": company,
                    "posted_date": posted_date,
                    "amount_cents": int(amount * 100),
                    "description": source_description,
                    "counterparty_name": "",  # No initials in BANK tab format
                    "hash_norm": content_hash,
                    "business_hash": business_hash,
                    "row_index_0based": row_index,
                    "source_stream_id": "petty_cash_csv",
                    "source_file_fingerprint": self.file_fingerprint,
                    "posted_flag": self._extract_posted_flag(row),
                    "raw_row": row
                }
            
            # Standard format: Extract employee initials from Column A
            initials = self._extract_initials(row)
            if not initials:
                return None
            
            # Extract company from Column C
            company = self._extract_company(row)
            if not company:
                return None
            
            # Parse transaction data
            posted_date = self._parse_date(row)
            amount = self._parse_amount(row)
            source_description = self._extract_source(row)
            
            if not posted_date or amount is None or not source_description:
                return None
            
            # Generate unique identifiers
            txn_uid = self._generate_txn_uid(company, row_index, posted_date, int(amount * 100), source_description)
            content_hash = self._generate_content_hash(company, posted_date, amount, source_description)
            business_hash = self._generate_business_hash(company, posted_date, amount, source_description)
            
            return {
                "txn_uid": txn_uid,
                "company_id": company,
                "posted_date": posted_date,
                "amount_cents": int(amount * 100),  # Convert to cents
                "description": source_description,
                "counterparty_name": initials,  # Employee initials as counterparty
                "hash_norm": content_hash,
                "business_hash": business_hash,
                "row_index_0based": row_index,
                "source_stream_id": "petty_cash_csv",
                "source_file_fingerprint": self.file_fingerprint,
                # Posted checkbox flag from column F
                "posted_flag": self._extract_posted_flag(row),
                "raw_row": row
            }
            
        except Exception as e:
            log.warning(f"Error parsing transaction row {row_index}: {e}")
            return None
    
    def _extract_initials(self, row: List[str]) -> Optional[str]:
        """Extract employee initials from Column A"""
        if len(row) <= self.column_mapping['initials']:
            return None
        
        initials = row[self.column_mapping['initials']].strip().upper()
        if not initials or len(initials) > 10:  # Reasonable limit for initials
            return None
        
        return initials
    
    def _extract_company(self, row: List[str]) -> Optional[str]:
        """Extract and validate company from Column C"""
        if len(row) <= self.column_mapping['company']:
            return None
        
        company = row[self.column_mapping['company']].strip().upper()
        # Accept common aliases and map to canonical company IDs used by the system
        alias_to_canonical = {
            'PUFFIN PURE': 'PUFFIN',
            'PUFFIN': 'PUFFIN',
            'EMPIRE': 'EMPIRE',
            '710 EMPIRE': 'EMPIRE',
            'NUGZ': 'NUGZ',
            'JGD': 'JGD',
        }
        company = alias_to_canonical.get(company, company)
        
        # Validate company against configured list
        if company not in self.valid_companies:
            log.debug(f"Invalid company '{company}' in row")
            return None
        
        return company
    
    def _parse_date_from_column(self, row: List[str], col_index: int) -> Optional[str]:
        """Parse date string from a specific column index to ISO format"""
        if len(row) <= col_index:
            return None
        
        date_str = row[col_index].strip()
        if not date_str:
            return None
        
        # Try configured date formats (with safe fallbacks)
        for fmt in self.date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        return None
    
    def _parse_date(self, row: List[str]) -> Optional[str]:
        """Parse date string from configured date column to ISO format"""
        return self._parse_date_from_column(row, self.column_mapping['date'])
    
    def _parse_amount(self, row: List[str]) -> Optional[float]:
        """Parse amount string from Column E to float"""
        if len(row) <= self.column_mapping['total']:
            return None
        
        amount_str = row[self.column_mapping['total']].strip()
        if not amount_str:
            return None
        
        # Remove currency symbols and commas (but keep decimal points)
        cleaned = re.sub(r'[$,]', '', amount_str).strip()
        # Treat dashes/empties as missing
        if cleaned == '' or cleaned == '-':
            return None
        
        # Handle negative amounts (parentheses or minus sign)
        is_negative = False
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = cleaned[1:-1]
            is_negative = True
        elif cleaned.startswith('-'):
            cleaned = cleaned[1:]
            is_negative = True
        
        try:
            amount = float(cleaned)
            return -amount if is_negative else amount
        except ValueError:
            log.warning(f"Could not parse amount: {amount_str}")
            return None
    
    def _extract_source(self, row: List[str]) -> str:
        """Extract source/description from Column D (exact as-is, no trim or case change)"""
        if len(row) <= self.column_mapping['source']:
            return ""
        return row[self.column_mapping['source']]
    
    def _generate_txn_uid(
        self,
        company: str,
        row_index_0based: int,
        posted_date: str,
        amount_cents: int,
        description: str,
    ) -> str:
        """Generate deterministic transaction UID with tenant/workbook boundaries.

        Includes:
          - company_id
          - source_spreadsheet_id (if known)
          - source_tab (if known)
          - row_index_0based (to disambiguate identical rows)
          - posted_date/amount/description (stability across reruns)
        """
        namespace = uuid.uuid5(uuid.NAMESPACE_URL, "kylo://txn_v2")
        desc_norm = re.sub(r"\s+", " ", (description or "").strip())
        payload = "|".join(
            [
                "petty_cash_csv",
                (company or "").strip().upper(),
                (self.source_spreadsheet_id or "").strip(),
                (self.source_tab or "").strip().upper(),
                str(int(row_index_0based)),
                str(posted_date or "").strip(),
                str(int(amount_cents or 0)),
                desc_norm,
            ]
        )
        return str(uuid.uuid5(namespace, payload))
    
    def _generate_content_hash(self, company: str, posted_date: str, amount: float, description: str) -> str:
        """Generate hash based on exact content (for content-level deduplication)"""
        desc_norm = re.sub(r"\s+", " ", (description or "").strip())
        payload = f"{posted_date}|{company}|{self.source_spreadsheet_id}|{self.source_tab}|{int(amount*100)}|{desc_norm}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def _generate_business_hash(self, company: str, posted_date: str, amount: float, description: str) -> str:
        """Generate hash based on business logic (normalized description, same day, same amount)"""
        # Normalize description for business matching
        normalized_desc = self._normalize_description(description)
        payload = f"{posted_date}|{company}|{self.source_spreadsheet_id}|{self.source_tab}|{int(amount*100)}|{normalized_desc}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
    
    def _normalize_description(self, description: str) -> str:
        """Normalize description for business-level deduplication"""
        # Remove common variations
        normalized = description.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        return normalized

    def _extract_posted_flag(self, row: List[str]) -> bool:
        idx = self.column_mapping.get('posted', 5)
        if len(row) <= idx:
            return False
        val = row[idx]
        if val is None:
            return False
        s = str(val).strip().upper()
        return s in ("TRUE", "1", "YES", "Y")
    
    def get_processing_stats(self) -> Dict:
        """Get processing statistics"""
        lines = self.csv_content.split('\n')
        data_lines = [line for line in lines[self.header_rows:] if line.strip()]
        
        return {
            'file_fingerprint': self.file_fingerprint,
            'total_lines': len(lines),
            'header_rows': self.header_rows,
            'data_rows': len(data_lines),
            'unique_rows_processed': len(self.seen_rows),
            'duplicate_rows_skipped': len(data_lines) - len(self.seen_rows)
        }

    def _load_valid_companies(self) -> set:
        """Load valid companies prioritizing YAML sheet keys, with legacy aliases included.

        Order of precedence:
          1) YAML sheets.companies keys (new canonical names, e.g., EMPIRE, PUFFIN)
          2) Union with config/companies.json company_id entries (legacy names)
          3) Fallback to csv_processor_config.json companies keys
          4) Final legacy defaults
        """
        names_yaml: set = set()
        names_json: set = set()
        names_cfg: set = set()

        # YAML first (authoritative naming)
        try:
            comps = ((self._yaml.get("sheets", {}) or {}).get("companies", []) or [])
            for it in comps:
                key = (it.get("key") or "").strip().upper()
                if key:
                    names_yaml.add("710 EMPIRE" if key == "710" else key)
        except Exception:
            pass

        # companies.json (legacy) — union, don't override
        try:
            companies_path = os.path.join("config", "companies.json")
            if os.path.exists(companies_path):
                with open(companies_path, "r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                items = data.get("companies") or []
                for it in items:
                    try:
                        cid = (it.get("company_id") or "").strip().upper()
                        if cid:
                            names_json.add(cid)
                    except Exception:
                        continue
        except Exception as e:
            log.debug("csv_processor: companies.json load failed: %s", e)

        # csv_processor_config.json companies section (optional)
        try:
            companies_cfg = self._config.get("companies") if isinstance(self._config, dict) else None
            if isinstance(companies_cfg, dict) and companies_cfg:
                for k in companies_cfg.keys():
                    if isinstance(k, str) and k.strip():
                        names_cfg.add(k.strip().upper())
        except Exception:
            pass

        # Build final set, prefer YAML, include legacy aliases
        final_names: set = set()
        final_names |= names_yaml or set()
        # If YAML declared new names, include their legacy counterparts for validation compatibility
        if "EMPIRE" in final_names:
            final_names.add("710 EMPIRE")
        if "PUFFIN" in final_names:
            final_names.add("PUFFIN PURE")
        # Union any discovered legacy sets
        final_names |= names_json
        final_names |= names_cfg

        if final_names:
            return final_names

        # Legacy default set
        return {'NUGZ', '710 EMPIRE', 'PUFFIN PURE', 'JGD'}


def parse_csv_transactions(csv_content: str, header_rows: int = 19, source_tab: Optional[str] = None) -> List[Dict]:
    """
    Convenience function to parse CSV and return all transactions
    
    Args:
        csv_content: CSV content as string
        header_rows: Number of header rows to skip
        source_tab: Optional source tab name (e.g., "BANK") for special handling
    
    Returns:
        List of parsed transactions
    """
    processor = PettyCashCSVProcessor(csv_content, header_rows, source_tab=source_tab)
    return list(processor.parse_transactions())


def validate_transaction(transaction: Dict) -> Tuple[bool, List[str]]:
    """
    Validate parsed transaction
    
    Args:
        transaction: Parsed transaction dictionary
    
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Required fields
    required_fields = ['txn_uid', 'company_id', 'posted_date', 'amount_cents', 'description']
    for field in required_fields:
        if field not in transaction or transaction[field] is None:
            errors.append(f"Missing required field: {field}")
    
    # Validate company using config-driven list with safe fallback
    try:
        def _load_valid_companies_global() -> set:
            names_yaml: set = set()
            try:
                from services.common.config_loader import load_config as _lc
                _y = _lc().data if hasattr(_lc(), 'data') else {}
                comps = ((_y.get("sheets", {}) or {}).get("companies", []) or [])
                for it in comps:
                    key = (it.get("key") or "").strip().upper()
                    if key:
                        names_yaml.add("710 EMPIRE" if key == "710" else key)
            except Exception:
                pass

            names_json: set = set()
            companies_path = os.path.join("config", "companies.json")
            try:
                if os.path.exists(companies_path):
                    with open(companies_path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                    items = data.get("companies") or []
                    for it in items:
                        try:
                            cid = (it.get("company_id") or "").strip().upper()
                            if cid:
                                names_json.add(cid)
                        except Exception:
                            continue
            except Exception:
                pass

            names_cfg: set = set()
            try:
                cfg_path = os.environ.get("KYLO_CSV_CONFIG_PATH", os.path.join("config", "csv_processor_config.json"))
                if os.path.exists(cfg_path):
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f) or {}
                    companies_cfg = cfg.get("companies")
                    if isinstance(companies_cfg, dict) and companies_cfg:
                        for k in companies_cfg.keys():
                            if isinstance(k, str) and k.strip():
                                names_cfg.add(k.strip().upper())
            except Exception:
                pass

            finals = set()
            finals |= names_yaml
            if "EMPIRE" in finals:
                finals.add("710 EMPIRE")
            if "PUFFIN" in finals:
                finals.add("PUFFIN PURE")
            finals |= names_json
            finals |= names_cfg
            if finals:
                return finals
            return {'NUGZ', '710 EMPIRE', 'PUFFIN PURE', 'JGD'}

        if 'company_id' in transaction:
            valid_companies = _load_valid_companies_global()
            if (transaction['company_id'] or '').strip().upper() not in valid_companies:
                errors.append(f"Invalid company: {transaction['company_id']}")
    except Exception:
        # If validation can't load configs, skip company validation (non-fatal)
        pass
    
    # Validate amount
    if 'amount_cents' in transaction:
        if not isinstance(transaction['amount_cents'], int):
            errors.append("Amount must be integer cents")
        elif transaction['amount_cents'] == 0:
            errors.append("Amount cannot be zero")
    
    # Validate date
    if 'posted_date' in transaction:
        try:
            datetime.strptime(transaction['posted_date'], '%Y-%m-%d')
        except ValueError:
            errors.append(f"Invalid date format: {transaction['posted_date']}")
    
    return len(errors) == 0, errors
