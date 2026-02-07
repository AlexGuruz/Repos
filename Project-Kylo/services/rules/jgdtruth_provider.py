from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List, Set
import os
import re

from services.common.config_loader import load_config
from services.common.retry import google_api_execute
from services.sheets.poster import _extract_spreadsheet_id, _get_service


@dataclass(frozen=True)
class Rule:
    source: str
    target_sheet: str
    target_header: str
    approved: bool
    company_id: Optional[str] = None  # Company ID filter (empty = applies to all companies)


def _normalize_source(value: str) -> str:
    return (value or "").strip().upper()


def _active_years(cfg) -> Optional[Set[int]]:
    """Return active years filter for year_workbooks, or None for 'no filtering'."""
    raw = (os.environ.get("KYLO_ACTIVE_YEARS") or "").strip()
    if raw:
        years: Set[int] = set()
        for part in re.split(r"[,\s]+", raw):
            if not part:
                continue
            if str(part).strip().isdigit():
                years.add(int(part))
        return years or None

    cfg_val = cfg.get("year_workbooks_active")
    if isinstance(cfg_val, list) and cfg_val:
        years = set()
        for it in cfg_val:
            try:
                years.add(int(str(it).strip()))
            except Exception:
                continue
        return years or None

    # Default: all configured years
    ym = cfg.get("year_workbooks") or {}
    if isinstance(ym, dict) and ym:
        years = set()
        for k in ym.keys():
            try:
                years.add(int(str(k).strip()))
            except Exception:
                continue
        return years or None
    return None


def fetch_rules_from_jgdtruth(company_id: Optional[str] = None) -> Dict[str, Rule]:
    """Load rules from the "JGD RULES" tab in the year workbook.
    
    Reads from year_workbooks[year].output_workbook_url (or intake_workbook_url as fallback),
    tab "JGD RULES". Uses active year from KYLO_ACTIVE_YEARS or year_workbooks_active config.
    Supports both 2025 and 2026 year workbooks.
    
    If multiple active years are configured, reads from the first active year's workbook.
    
    Sheet shape:
      - Column A: Unique Source
      - Column B: Target sheet
      - Column C: Target Header
      - Column D (aka STATUS): Approved checkbox (TRUE/FALSE)
      - Column E: Company ID (optional - empty means rule applies to all companies)
    
    If company_id is provided, only returns rules where:
      - Rule's Company ID column is empty/blank (applies to all)
      - OR Rule's Company ID matches the provided company_id (case-insensitive)
    """
    if not company_id:
        raise RuntimeError("company_id is required to fetch rules from year workbook")
    
    cfg = load_config()
    
    # Get active year from env or config (KYLO_ACTIVE_YEARS env var or year_workbooks_active config)
    # This ensures each watcher instance (KYLO_2025, KYLO_2026) reads from its correct year workbook
    active_years = _active_years(cfg)  # Returns Set[int] or None
    
    # Determine which year workbook to use
    workbook_url = None
    selected_year = None
    if active_years:
        # Use first active year's workbook (sorted to ensure consistent ordering)
        # For KYLO_2025 watcher: active_years = {2025} → reads from year_workbooks.2025
        # For KYLO_2026 watcher: active_years = {2026} → reads from year_workbooks.2026
        selected_year = sorted(list(active_years))[0]
        workbook_url = cfg.get(f"year_workbooks.{selected_year}.output_workbook_url")
        if not workbook_url:
            workbook_url = cfg.get(f"year_workbooks.{selected_year}.intake_workbook_url")
    
    # Fallback to company workbook if year_workbooks not configured
    if not workbook_url:
        companies = cfg.get("sheets.companies") or []
        company_upper = company_id.strip().upper()
        comp = None
        for it in companies:
            key = (it.get("key") or "").strip().upper()
            if key == company_upper:
                comp = it
                break
            if company_upper == "710" and key == "710":
                comp = it
                break
        
        if not comp:
            raise RuntimeError(f"Company '{company_id}' not found in config.sheets.companies")
        
        workbook_url = comp.get("workbook_url")
        if not workbook_url:
            raise RuntimeError(f"workbook_url not set for company '{company_id}' in config")
    
    sid = _extract_spreadsheet_id(str(workbook_url))
    if selected_year:
        print(f"[RULES] Loading rules for company '{company_id}' from year {selected_year} workbook -> 'JGD RULES' tab")
    service = _get_service()

    approved_idx = 3  # Column D for approved status (default)
    company_id_idx = 4  # Column E for company ID (default)

    def _try_fetch(tab_range: str) -> Optional[List[List[object]]]:
        try:
            req = service.spreadsheets().values().get(
                spreadsheetId=sid,
                range=tab_range,
                valueRenderOption="UNFORMATTED_VALUE",
            )
            resp_local = google_api_execute(req, label=f"rules:{tab_range}")
            return resp_local.get("values", [])
        except Exception:
            return None

    # Read from "JGD RULES" tab in the year workbook (supports both 2025 and 2026)
    values: List[List[object]] = []
    got = _try_fetch("'JGD RULES'!A1:E10000")  # Read columns A through E
    if isinstance(got, list):
        values = got
    else:
        # Fallback: try without quotes (some API versions don't need quotes)
        got = _try_fetch("JGD RULES!A1:E10000")
        if isinstance(got, list):
            values = got
        else:
            # Fallback: try legacy "JGD" tab name
            approved_idx = 5  # legacy F
            got = _try_fetch("JGD!A1:F10000")
            values = got or []

    rules: Dict[str, Rule] = {}
    header: List[str] = []
    ignore_approved = (os.environ.get("KYLO_RULES_IGNORE_APPROVED", "") or "").strip().lower() in ("1", "true", "yes", "y")
    
    # Normalize company_id for matching
    requested_company_upper = (company_id or "").strip().upper() if company_id else None
    
    for i, row in enumerate(values):
        if i == 0:
            # Parse header row to find column indices dynamically
            header = [str(x).strip() for x in row]
            def _col_idx(name: str) -> int:
                try:
                    return [h.lower() for h in header].index(name.lower())
                except Exception:
                    return -1

            # Find Approved column (STATUS or Approved)
            appr_by_name = _col_idx("STATUS")
            if appr_by_name < 0:
                appr_by_name = _col_idx("Approved")
            if appr_by_name >= 0:
                approved_idx = appr_by_name
            
            # Find Company ID column (Company_ID, Company ID, Company, etc.)
            company_by_name = _col_idx("Company_ID")
            if company_by_name < 0:
                company_by_name = _col_idx("Company ID")
            if company_by_name < 0:
                company_by_name = _col_idx("Company")
            if company_by_name >= 0:
                company_id_idx = company_by_name
            continue

        # Extract columns with bounds checks
        src = row[0] if len(row) > 0 and row[0] is not None else ""
        tgt_sheet = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
        tgt_header = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
        approved_cell = row[approved_idx] if len(row) > approved_idx else None
        
        # Extract Company ID (Column E, or detected column)
        rule_company_id = ""
        if len(row) > company_id_idx:
            rule_company_id = str(row[company_id_idx]).strip() if row[company_id_idx] is not None else ""
        rule_company_upper = rule_company_id.upper()

        # Filter by company_id if provided
        if requested_company_upper:
            # Rule applies if:
            # 1. Rule's company_id is empty (applies to all companies)
            # 2. Rule's company_id matches requested company (case-insensitive)
            if rule_company_upper and rule_company_upper != requested_company_upper:
                continue  # Skip this rule - doesn't match company filter

        approved = False
        if isinstance(approved_cell, bool):
            approved = approved_cell
        else:
            try:
                approved = str(approved_cell).strip().upper() == "TRUE"
            except Exception:
                approved = False
        if ignore_approved:
            approved = True

        if not src:
            continue
        
        # Use source as key, but allow duplicates if they have different company_ids
        # For same source with different companies, we'll match by company filter above
        rule_key = str(src)
        rules[rule_key] = Rule(
            source=str(src),
            target_sheet=tgt_sheet,
            target_header=tgt_header,
            approved=approved,
            company_id=rule_company_id if rule_company_id else None,
        )
    
    return rules


__all__ = ["Rule", "fetch_rules_from_jgdtruth"]


