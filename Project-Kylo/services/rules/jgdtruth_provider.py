from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import os
import re

from services.common.config_loader import load_config
from services.common.retry import google_api_execute
from services.common.rules_workbook import get_rules_management_spreadsheet_id
from services.sheets.poster import _extract_spreadsheet_id, _get_service


@dataclass(frozen=True)
class Rule:
    source: str
    target_sheet: str
    target_header: str
    approved: bool
    company_id: Optional[str] = None  # Company ID filter (empty = applies to all companies)
    pool: Optional[str] = None  # CASH | BANK | TRANSFER (sandbox dual-rule schema)
    event_type: Optional[str] = None  # OPERATING | TRANSFER_* | OPENING | ADJUSTMENT | TILL
    intake_tab: Optional[str] = None  # TRANSACTIONS | BANK


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


def _quote_tab_a1(name: str) -> str:
    import re as _re

    s = str(name or "")
    if _re.search(r"[^A-Za-z0-9_]", s):
        return "'" + s.replace("'", "''") + "'"
    return s


def _active_tab_candidates(company_id: str) -> List[str]:
    company_upper = (company_id or "").strip().upper()
    names = [f"{company_upper} Active"]
    if company_upper == "EMPIRE":
        names.extend(["710 Active", "710 EMPIRE Active"])
    elif company_upper == "PUFFIN":
        names.extend(["PUFFIN PURE Active"])
    return names


def _sheet_values(service, spreadsheet_id: str, tab_range: str) -> Optional[List[List[object]]]:
    try:
        req = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=tab_range,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        resp_local = google_api_execute(req, label=f"rules:{tab_range}")
        return resp_local.get("values", [])
    except Exception:
        return None


def _col_idx(header: List[str], *names: str) -> int:
    lowered = [h.lower() for h in header]
    for name in names:
        try:
            return lowered.index(name.lower())
        except ValueError:
            continue
    return -1


def _parse_rules_rows(
    values: List[List[object]],
    *,
    company_id: Optional[str],
    default_approved: bool = False,
    source_default_col: int = 0,
    target_sheet_default_col: int = 1,
    target_header_default_col: int = 2,
    approved_default_col: int = 3,
    company_default_col: int = 4,
) -> Dict[str, Rule]:
    rules: Dict[str, Rule] = {}
    header: List[str] = []
    ignore_approved = (os.environ.get("KYLO_RULES_IGNORE_APPROVED", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "y",
    )
    requested_company_upper = (company_id or "").strip().upper() if company_id else None

    approved_idx = approved_default_col
    company_id_idx = company_default_col
    source_idx = source_default_col
    target_sheet_idx = target_sheet_default_col
    target_header_idx = target_header_default_col
    pool_idx = -1
    event_idx = -1
    intake_idx = -1

    for i, row in enumerate(values):
        if i == 0:
            header = [str(x).strip() for x in row]
            src_by_name = _col_idx(header, "Source", "Unique Source")
            if src_by_name >= 0:
                source_idx = src_by_name
            sheet_by_name = _col_idx(header, "Target_Sheet", "Target sheet", "Target Sheet")
            if sheet_by_name >= 0:
                target_sheet_idx = sheet_by_name
            header_by_name = _col_idx(header, "Target_Header", "Target header", "Target Header")
            if header_by_name >= 0:
                target_header_idx = header_by_name
            appr_by_name = _col_idx(header, "STATUS", "Approved", "APPROVED")
            if appr_by_name >= 0:
                approved_idx = appr_by_name
            company_by_name = _col_idx(header, "Company_ID", "Company ID", "Company", "COMPANY ID")
            if company_by_name >= 0:
                company_id_idx = company_by_name
            pool_idx = _col_idx(header, "Pool", "POOL")
            event_idx = _col_idx(header, "Event Type", "Event_Type", "EVENT TYPE")
            intake_idx = _col_idx(header, "Intake Tab", "Intake_Tab", "INTAKE TAB")
            continue

        src = row[source_idx] if len(row) > source_idx and row[source_idx] is not None else ""
        tgt_sheet = str(row[target_sheet_idx]).strip() if len(row) > target_sheet_idx and row[target_sheet_idx] is not None else ""
        tgt_header = (
            str(row[target_header_idx]).strip() if len(row) > target_header_idx and row[target_header_idx] is not None else ""
        )
        approved_cell = row[approved_idx] if len(row) > approved_idx else None

        rule_company_id = ""
        if len(row) > company_id_idx:
            rule_company_id = str(row[company_id_idx]).strip() if row[company_id_idx] is not None else ""
        rule_company_upper = rule_company_id.upper()

        if requested_company_upper:
            if rule_company_upper and rule_company_upper != requested_company_upper:
                continue

        if default_approved or ignore_approved:
            approved = True
        elif isinstance(approved_cell, bool):
            approved = approved_cell
        else:
            try:
                approved = str(approved_cell).strip().upper() == "TRUE"
            except Exception:
                approved = False

        if not src:
            continue

        pool = None
        if pool_idx >= 0 and len(row) > pool_idx and row[pool_idx] is not None:
            pool = str(row[pool_idx]).strip().upper() or None
        event_type = None
        if event_idx >= 0 and len(row) > event_idx and row[event_idx] is not None:
            event_type = str(row[event_idx]).strip().upper() or None
        intake_tab = None
        if intake_idx >= 0 and len(row) > intake_idx and row[intake_idx] is not None:
            intake_tab = str(row[intake_idx]).strip().upper() or None

        rule_key = str(src)
        rules[rule_key] = Rule(
            source=str(src),
            target_sheet=tgt_sheet,
            target_header=tgt_header,
            approved=approved,
            company_id=rule_company_id if rule_company_id else None,
            pool=pool,
            event_type=event_type,
            intake_tab=intake_tab,
        )

    return rules


def _fetch_rules_from_management_active(cfg, company_id: str) -> Tuple[Dict[str, Rule], Optional[str]]:
    sid = get_rules_management_spreadsheet_id(cfg)
    if not sid:
        return {}, None

    service = _get_service()
    for tab in _active_tab_candidates(company_id):
        values = _sheet_values(service, sid, f"{_quote_tab_a1(tab)}!A1:H10000")
        if not values:
            values = _sheet_values(service, sid, f"{tab}!A1:H10000")
        if values and len(values) > 1:
            rules = _parse_rules_rows(values, company_id=company_id, default_approved=True)
            if rules:
                return rules, tab
    return {}, None


def _fetch_rules_from_year_workbook(
    cfg,
    company_id: str,
    *,
    rules_tab_override: Optional[str] = None,
) -> Tuple[Dict[str, Rule], Optional[str], Optional[int]]:
    active_years = _active_years(cfg)
    workbook_url = None
    selected_year = None
    if active_years:
        selected_year = sorted(list(active_years))[0]
        workbook_url = cfg.get(f"year_workbooks.{selected_year}.output_workbook_url")
        if not workbook_url:
            workbook_url = cfg.get(f"year_workbooks.{selected_year}.intake_workbook_url")

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
    cfg_rules_tab = (rules_tab_override or cfg.get("rules.rules_tab_name") or "").strip()
    rules_tab = cfg_rules_tab or "JGD RULES"
    service = _get_service()

    values: List[List[object]] = []
    # A:I covers sandbox Pool / Event Type / Intake Tab columns
    got = _sheet_values(service, sid, f"{_quote_tab_a1(rules_tab)}!A1:I10000")
    if isinstance(got, list):
        values = got
    else:
        got = _sheet_values(service, sid, f"{rules_tab}!A1:I10000")
        if isinstance(got, list):
            values = got
        else:
            got = _sheet_values(service, sid, "'JGD RULES'!A1:I10000")
            if not isinstance(got, list):
                got = _sheet_values(service, sid, "JGD RULES!A1:I10000")
            if not isinstance(got, list):
                got = _sheet_values(service, sid, "JGD!A1:F10000")
            values = got or []

    rules = _parse_rules_rows(values, company_id=company_id, default_approved=False)
    return rules, rules_tab, selected_year


def fetch_rules_from_jgdtruth(company_id: Optional[str] = None) -> Dict[str, Rule]:
    """Load rules live from Google Sheets.

    Sources (merged, year workbook wins on duplicate source keys):
      1. Rules management workbook -> ``{CID} Active`` tab (when configured)
      2. Year workbook -> ``JGD RULES`` tab (or ``rules.rules_tab_name``)
    """
    if not company_id:
        raise RuntimeError("company_id is required to fetch rules from year workbook")

    cfg = load_config()
    merged: Dict[str, Rule] = {}

    active_rules, active_tab = _fetch_rules_from_management_active(cfg, company_id)
    if active_rules:
        print(
            f"[RULES] Loaded {len(active_rules)} rules for company '{company_id}' "
            f"from rules management workbook -> '{active_tab}' tab"
        )
        merged.update(active_rules)

    year_rules, rules_tab, selected_year = _fetch_rules_from_year_workbook(cfg, company_id)
    if year_rules:
        if selected_year:
            print(
                f"[RULES] Loaded {len(year_rules)} rules for company '{company_id}' "
                f"from year {selected_year} workbook -> '{rules_tab}' tab"
            )
        else:
            print(
                f"[RULES] Loaded {len(year_rules)} rules for company '{company_id}' "
                f"from company workbook -> '{rules_tab}' tab"
            )
        merged.update(year_rules)

    if not merged:
        raise RuntimeError(f"No rules found for company '{company_id}' in management Active or year workbook tabs")

    return merged


def fetch_rules_by_intake_tab(company_id: Optional[str] = None) -> Dict[str, Dict[str, Rule]]:
    """Load rules keyed by intake tab (TRANSACTIONS / BANK).

    When ``rules.bank_rules_tab_name`` is set (sandbox dual-rule mode), loads separate
    year-workbook tabs for TRANSACTIONS and BANK. Otherwise both keys resolve to the
    same merged dict from ``fetch_rules_from_jgdtruth`` (legacy behaviour).
    """
    if not company_id:
        raise RuntimeError("company_id is required to fetch rules from year workbook")

    cfg = load_config()
    bank_tab = (cfg.get("rules.bank_rules_tab_name") or "").strip()
    tx_tab = (cfg.get("rules.rules_tab_name") or "").strip() or "JGD RULES"

    if not bank_tab:
        shared = fetch_rules_from_jgdtruth(company_id)
        return {"TRANSACTIONS": shared, "BANK": shared}

    # Dual-tab mode: management Active still merges under TRANSACTIONS as base books rules,
    # then each year tab overwrites for its intake.
    base: Dict[str, Rule] = {}
    active_rules, active_tab = _fetch_rules_from_management_active(cfg, company_id)
    if active_rules:
        print(
            f"[RULES] Dual-mode: management Active '{active_tab}' -> {len(active_rules)} base rules"
        )
        base.update(active_rules)

    tx_rules, loaded_tx_tab, yr = _fetch_rules_from_year_workbook(
        cfg, company_id, rules_tab_override=tx_tab
    )
    bank_rules, loaded_bank_tab, _yr2 = _fetch_rules_from_year_workbook(
        cfg, company_id, rules_tab_override=bank_tab
    )

    tx_merged = dict(base)
    tx_merged.update(tx_rules or {})
    bank_merged = dict(base)
    bank_merged.update(bank_rules or {})

    if not tx_merged and not bank_merged:
        raise RuntimeError(
            f"No dual rules found for '{company_id}' in tabs '{tx_tab}' / '{bank_tab}'"
        )

    # If one tab missing, fall back that side to the other so posting still works.
    if not tx_merged and bank_merged:
        tx_merged = dict(bank_merged)
    if not bank_merged and tx_merged:
        bank_merged = dict(tx_merged)

    print(
        f"[RULES] Dual-mode year={yr}: TRANSACTIONS '{loaded_tx_tab}'={len(tx_merged)} "
        f"BANK '{loaded_bank_tab}'={len(bank_merged)}"
    )
    return {"TRANSACTIONS": tx_merged, "BANK": bank_merged}


__all__ = ["Rule", "fetch_rules_from_jgdtruth", "fetch_rules_by_intake_tab"]
