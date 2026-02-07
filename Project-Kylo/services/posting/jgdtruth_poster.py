from __future__ import annotations

import argparse
import os
import json
import re
import unicodedata
from datetime import date, timedelta
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from services.common.config_loader import load_config
from services.rules.jgdtruth_provider import fetch_rules_from_jgdtruth
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.state.store import (
    State,
    StateError,
    compute_cell_key,
    compute_signature,
    load_state,
    save_state,
)
from services.common.retry import google_api_execute
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions

try:
    from googleapiclient.errors import HttpError
except ImportError:
    # Fallback if not available
    HttpError = Exception


def _col_to_a1(col_index_0: int) -> str:
    # 0->A, 1->B, ...
    s = ""
    n = col_index_0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _quote_tab_a1(name: str) -> str:
    """Quote a sheet tab title for A1 notation when needed.

    The Sheets API requires quotes around tab names that contain spaces or
    special characters, e.g. "'NUGZ EXPENSES'!A1".
    """
    s = str(name or "")
    if re.search(r"[^A-Za-z0-9_]", s):
        return "'" + s.replace("'", "''") + "'"
    return s


def _build_date_row_map(dates: List[str], header_row: int, first_row: int) -> Dict[str, int]:
    # Date format is as provided by user; exact string match
    return {d: (first_row + i) for i, d in enumerate(dates)}


def _parse_mdy_yy(mdy: str) -> Optional[date]:
    """Parse M/D/YY (no leading zeros required) to a date."""
    try:
        m, d, yy = str(mdy).strip().split("/")
        return date(2000 + int(yy), int(m), int(d))
    except Exception:
        return None


def _format_mdy_yy(dt: date) -> str:
    """Format date as M/D/YY (no leading zeros)."""
    return f"{dt.month}/{dt.day}/{dt.year % 100:02d}"


def _extend_static_dates(cfg, dates: List[str]) -> List[str]:
    """Extend the static dates list forward through Dec 31 of configured year."""
    try:
        through_year = cfg.get("intake_static_dates.generate_through_year")
        if through_year is None:
            return dates
        through_year_int = int(through_year)
        if through_year_int < 2000:
            return dates
    except Exception:
        return dates

    if not dates:
        return dates
    last = _parse_mdy_yy(dates[-1])
    if not last:
        return dates

    end = date(through_year_int, 12, 31)
    if last >= end:
        return dates

    out = list(dates)
    cur = last + timedelta(days=1)
    while cur <= end:
        out.append(_format_mdy_yy(cur))
        cur += timedelta(days=1)
    return out


def _resolve_year_workbook_url(cfg, year: int, which: str) -> Optional[str]:
    """Resolve year_workbooks.<year>.<which> as a string URL/ID if present."""
    try:
        return cfg.get(f"year_workbooks.{int(year)}.{which}")
    except Exception:
        return None


## Date rows are static; do not read dates via API


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

    # Default: all configured years (preserve prior behavior)
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


def _ensure_transactions_append(service, spreadsheet_id: str, rows: List[List[object]]) -> None:
    if not rows:
        return
    req = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range="TRANSACTIONS!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    )
    google_api_execute(req, label="append:transactions")


def _read_header_row(service, spreadsheet_id: str, tab: str, header_row: int) -> List[str]:
    qt = _quote_tab_a1(tab)
    rng = f"{qt}!1:1" if header_row == 1 else f"{qt}!{header_row}:{header_row}"
    req = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueRenderOption="UNFORMATTED_VALUE",
    )
    res = google_api_execute(req, label="read:header_row")
    vals = res.get("values", [])
    return [str(c).strip() for c in (vals[0] if vals else [])]


def _a1_col(col_index_0: int) -> str:
    """0-based column index to A1 letters (A, B, ..., AA)."""
    return _col_to_a1(int(col_index_0))


def _find_header_col(headers: List[str], candidates: List[str]) -> Optional[int]:
    """Return 0-based column index of the first matching header name."""
    norm = [str(h).strip().lower() for h in (headers or [])]
    for name in candidates:
        want = str(name).strip().lower()
        if not want:
            continue
        if want in norm:
            return norm.index(want)
    return None


def _batch_read_headers(service, spreadsheet_id: str, tabs: List[str], header_row: int) -> Dict[str, List[str]]:
    """Read header row for multiple tabs in a single batchGet call.

    Returns a mapping tab_title -> header_cells(list[str]).
    """
    if not tabs:
        return {}
    ranges = [f"{_quote_tab_a1(t)}!1:1" if header_row == 1 else f"{_quote_tab_a1(t)}!{header_row}:{header_row}" for t in tabs]
    req = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=ranges,
        valueRenderOption="UNFORMATTED_VALUE",
    )
    resp = google_api_execute(req, label="batchGet:headers")
    out: Dict[str, List[str]] = {}
    value_ranges = resp.get("valueRanges", [])
    for r in value_ranges:
        rng = r.get("range", "")
        # Extract tab name before '!'
        tab_name = rng.split("!")[0].strip("'")
        vals = r.get("values", [])
        out[tab_name] = [str(c).strip() for c in (vals[0] if vals else [])]
    return out


def _normalize_text(value: str) -> str:
    if value is None:
        return ""
    s = str(value)
    # unicode normalize
    s = unicodedata.normalize("NFKC", s)
    # replace common zero-width/nbsp
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _batch_read_headers(service, spreadsheet_id: str, tabs: List[str], header_row: int) -> Dict[str, List[str]]:
    """Read header row for multiple tabs in a single batchGet call.

    Returns a mapping tab_title -> header_cells(list[str]).
    """
    if not tabs:
        return {}
    ranges = [f"{_quote_tab_a1(t)}!1:1" if header_row == 1 else f"{_quote_tab_a1(t)}!{header_row}:{header_row}" for t in tabs]
    resp = google_api_execute(
        service.spreadsheets()
        .values()
        .batchGet(spreadsheetId=spreadsheet_id, ranges=ranges, valueRenderOption="UNFORMATTED_VALUE"),
        label="batchGet:headers",
    )
    out: Dict[str, List[str]] = {}
    value_ranges = resp.get("valueRanges", [])
    for r in value_ranges:
        rng = r.get("range", "")
        # Extract tab name before '!'
        tab_name = rng.split("!")[0].strip("'")
        vals = r.get("values", [])
        out[tab_name] = [str(c).strip() for c in (vals[0] if vals else [])]
    return out


def run(company: str, *, baseline: bool = False, verify: Optional[bool] = None, rules_changed: bool = False):
    cfg = load_config()
    companies = cfg.get("sheets.companies") or []
    requested_key = company.strip().upper()
    comp = None
    for it in companies:
        key = (it.get("key") or "").strip().upper()
        if key == requested_key:
            comp = it
            break
        if requested_key == "710" and key == "710":
            comp = it
            break
    if not comp:
        raise SystemExit(f"Unknown company: {company}")

    company_key = (comp.get("key") or "").strip().upper()
    company_upper = company_key
    # Optional: collect a dry-run write plan for inspection (no API writes).
    # Enabled by setting KYLO_WRITE_PLAN_PATH to a file path.
    write_plan: List[Dict[str, Any]] = []

    baseline_flag = baseline or os.environ.get("KYLO_POST_BASELINE", "").lower() in ("1", "true", "yes", "y")
    # Auto-enable reprocessing if baseline is set (forces full reprocess)
    ignore_posted_flag = baseline_flag or os.environ.get("KYLO_IGNORE_POSTED_FLAG", "").lower() in ("1", "true", "yes", "y") or os.environ.get("KYLO_REPROCESS_POSTED", "").lower() in ("1", "true", "yes", "y")
    if verify is None:
        verify_flag = os.environ.get("KYLO_VERIFY_POST", "").lower() in ("1", "true", "yes", "y")
    else:
        verify_flag = bool(verify)

    try:
        state = load_state()
    except StateError as exc:
        print(f"[WARN] unable to load posting state: {exc}; starting with fresh state.")
        state = State()

    if baseline_flag or rules_changed:
        # Discard previous signatures so the baseline run reseeds them.
        # Also clear when rules change to force re-evaluation of all transactions.
        state.cell_signatures.pop(company_key, None)
        if rules_changed:
            # Clear skipped transactions so they get re-evaluated with new rules
            state.clear_skipped(company_key)
            print(f"[RULE CHANGE] Cleared signatures and skipped transactions for {company_key}")

    # Default output workbook (used when year_workbooks is not configured for a txn year)
    spreadsheet_id = _extract_spreadsheet_id(str(comp.get("workbook_url")))
    service_account = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "secrets/service_account.json")

    # Load transactions (CSV → parsed)
    # If year_workbooks is configured, pull from active year intake workbooks and route later by txn year.
    active_years = _active_years(cfg)
    year_intake_urls: List[str] = []
    try:
        ym = cfg.get("year_workbooks") or {}
        if isinstance(ym, dict):
            for y, spec in ym.items():
                try:
                    yi = int(str(y).strip())
                except Exception:
                    continue
                if active_years and yi not in active_years:
                    continue
                if isinstance(spec, dict):
                    u = spec.get("intake_workbook_url")
                else:
                    u = cfg.get(f"year_workbooks.{yi}.intake_workbook_url")
                if u and str(u).strip():
                    year_intake_urls.append(str(u).strip())
    except Exception:
        year_intake_urls = []
    if not year_intake_urls:
        intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
        year_intake_urls = [str(intake_url)]
    intake_sids = [_extract_spreadsheet_id(u) for u in year_intake_urls if str(u).strip()]
    print(f"[INTAKE] CSV download sources for {company_upper} (active_years={active_years}): {year_intake_urls}")
    print(f"[INTAKE] Spreadsheet IDs: {intake_sids}")

    # Merge intake from TRANSACTIONS, BANK, and any configured extra tabs, tagging source_tab + source_spreadsheet_id
    csv_txns: List[dict] = []
    extra_tabs: List[str] = []
    try:
        extra_tabs = [str(t) for t in (cfg.get("intake.extra_tabs") or []) if str(t).strip()]
    except Exception:
        extra_tabs = []
    tabs_to_pull = tuple(["TRANSACTIONS", "BANK"]) + tuple(extra_tabs)
    for sid in intake_sids:
        for tab in tabs_to_pull:
            try:
                print(f"[INTAKE] Downloading CSV from spreadsheet_id={sid} tab='{tab}'")
                csv_content = download_petty_cash_csv(sid, service_account, sheet_name_override=tab)
                # Pass source_tab to processor so it can handle BANK tab's different column structure
                from services.intake.csv_processor import PettyCashCSVProcessor
                processor = PettyCashCSVProcessor(
                    csv_content,
                    header_rows=int(cfg.get("intake.csv_processor.header_rows", 19)),
                    source_tab=tab,
                    source_spreadsheet_id=sid,
                )
                part = list(processor.parse_transactions())
                for it in part:
                    it["source_tab"] = tab
                    it["source_spreadsheet_id"] = sid
                csv_txns.extend(part)
            except Exception:
                # If a tab is missing, continue with the other
                continue
    
    # Sort transactions to ensure consistent processing order:
    # 1. By posted_date (chronological)
    # 2. By source_tab (consistent tab order)
    # 3. By row_index_0based (row order within tab)
    def _sort_key(t: dict) -> tuple:
        posted_date = t.get("posted_date") or ""
        source_tab = str(t.get("source_tab") or "").strip()
        row_idx = int(t.get("row_index_0based") or 0)
        # Ensure consistent tab ordering: TRANSACTIONS first, then BANK, then others
        tab_order = {"TRANSACTIONS": 0, "BANK": 1}.get(source_tab.upper(), 2)
        return (posted_date, tab_order, source_tab, row_idx)
    
    txns = sorted(csv_txns, key=_sort_key)
    print(f"[INTAKE] Loaded {len(txns)} total transactions from CSV")

    # If we have an active year filter, ignore transactions outside of it.
    if active_years:
        filtered: List[dict] = []
        filtered_out: int = 0
        for t in txns:
            dt = str(t.get("posted_date") or "").strip()
            yr: Optional[int] = None
            # Accept either ISO-ish "YYYY-..." or Sheets-style "M/D/YY" / "M/D/YYYY".
            if len(dt) >= 4 and dt[:4].isdigit():
                try:
                    yr = int(dt[:4])
                except Exception:
                    yr = None
            elif "/" in dt:
                try:
                    parts = dt.split("/")
                    tail = parts[-1].strip()
                    if tail.isdigit():
                        if len(tail) == 2:
                            yr = 2000 + int(tail)
                        elif len(tail) == 4:
                            yr = int(tail)
                except Exception:
                    yr = None
            if (yr is not None) and (yr in active_years):
                filtered.append(t)
            elif yr is not None:
                filtered_out += 1
            else:
                # If no year can be inferred, include it (let downstream decide).
                filtered.append(t)
        print(f"[INTAKE] Active years filter ({active_years}): kept {len(filtered)}, filtered out {filtered_out} transactions")
        txns = filtered

    # Load rules from JGD tab, filtered by company
    rules = fetch_rules_from_jgdtruth(company_upper)
    print(f"[INFO] Loaded {len(rules)} rules from JGD tab (filtered for company: {company_upper})")
    # Build a trim-only lookup (case-insensitive) to tolerate stray spaces and case differences
    rules_by_trim: Dict[str, any] = {}
    rules_by_trim_upper: Dict[str, any] = {}  # Case-insensitive lookup
    approved_rules = [r for r in rules.values() if r.approved]
    for r in approved_rules:
        key = (r.source or "").strip()
        if key:
            if key not in rules_by_trim:
                rules_by_trim[key] = r
            # Also store case-insensitive version
            key_upper = key.upper()
            if key_upper not in rules_by_trim_upper:
                rules_by_trim_upper[key_upper] = r
    
    # Diagnostic: report on approved rules status
    incomplete_rules = [r for r in approved_rules if not r.target_sheet or not r.target_header]
    if incomplete_rules:
        print(f"[WARN] Found {len(incomplete_rules)} approved rules missing target_sheet or target_header:")
        for r in incomplete_rules[:10]:
            missing = []
            if not r.target_sheet:
                missing.append("target_sheet")
            if not r.target_header:
                missing.append("target_header")
            print(f"  - '{r.source[:50]}' missing: {', '.join(missing)}")
        if len(incomplete_rules) > 10:
            print(f"  ... and {len(incomplete_rules) - 10} more")
    print(f"[INFO] Loaded {len(approved_rules)} approved rules ({len(rules_by_trim)} unique sources)")

    # Base static dates (M/D/YY) used for the legacy (2025) workbook mapping.
    # IMPORTANT: when routing by year to separate workbooks (2025 vs 2026),
    # we must NOT append 2026 dates to the 2025 mapping — otherwise 2026 rows
    # land "after" the entire 2025 block at the bottom of the new sheet.
    static_dates = (
        cfg.get("intake.static_dates")
        or cfg.get("intake_static_dates.dates", [])
        or []
    )
    has_year_routing = bool(
        cfg.get("year_workbooks.2025.output_workbook_url")
        or cfg.get("year_workbooks.2026.output_workbook_url")
        or cfg.get("year_workbooks.2025.intake_workbook_url")
        or cfg.get("year_workbooks.2026.intake_workbook_url")
    )
    if isinstance(static_dates, list) and not has_year_routing:
        # Single-workbook mode: safe to extend forward
        static_dates = _extend_static_dates(cfg, list(static_dates))
    # Lock header and first data rows per spec
    header_row = int(cfg.get("intake_static_dates.header_row", 19))
    first_row = int(cfg.get("intake_static_dates.first_row", 20))
    # NOTE: we build dates_to_row per-target workbook inside _process_target.

    service = _get_service()

    def _norm_tab_key(value: str) -> str:
        s = str(value)
        try:
            s = unicodedata.normalize("NFKC", s)
        except Exception:
            pass
        # replace zero-width and NBSP with regular space, trim and lower
        s = s.replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    def _quote_tab_for_a1(name: str) -> str:
        """Quote a tab name for A1 notation when needed (spaces/special chars)."""
        s = str(name)
        if re.search(r"[^A-Za-z0-9_]", s):
            return "'" + s.replace("'", "''") + "'"
        return s

    # Company-specific relax flags
    relaxed_companies = set([c.strip().upper() for c in (cfg.get("matching.relaxed_companies", ["EMPIRE", "PUFFIN"]))])
    relaxed_dates_companies = set([c.strip().upper() for c in (cfg.get("dates.relaxed_companies", ["EMPIRE", "PUFFIN"]))])

    # Get previously skipped transactions if rules changed
    previously_skipped: Set[str] = set()
    if rules_changed:
        previously_skipped = state.get_skipped(company_upper)
        if previously_skipped:
            print(f"[RULE CHANGE] Re-evaluating {len(previously_skipped)} previously skipped transactions")
    # Route by transaction year to a target spreadsheet (e.g., 2026 -> new) when configured.
    txns_by_target_sid: Dict[str, List[dict]] = defaultdict(list)
    years_by_target_sid: Dict[str, Set[int]] = defaultdict(set)
    for t in txns:
        dt = str(t.get("posted_date") or "").strip()  # YYYY-MM-DD
        year = None
        try:
            if len(dt) >= 4 and dt[0:4].isdigit():
                year = int(dt[0:4])
        except Exception:
            year = None
        # If active_years is set, skip any out-of-scope years defensively.
        if active_years and year is not None and year not in active_years:
            continue
        target_url = _resolve_year_workbook_url(cfg, year, "output_workbook_url") if year else None
        target_sid = _extract_spreadsheet_id(str(target_url)) if target_url else spreadsheet_id
        txns_by_target_sid[target_sid].append(t)
        if year is not None:
            years_by_target_sid[target_sid].add(int(year))

    # High-signal routing diagnostics: which workbook(s) we will write to.
    try:
        total_routed = 0
        for sid, items in txns_by_target_sid.items():
            yrs = sorted(list(years_by_target_sid.get(sid, set())))
            yr_txt = ",".join(str(y) for y in yrs) if yrs else "<unknown>"
            print(f"[TARGET] company={company_upper} target_spreadsheet_id={sid} txn_years={yr_txt} txns={len(items)}")
            total_routed += len(items)
        if total_routed == 0:
            print(f"[TARGET] WARN: No transactions routed to any target workbook for {company_upper}")
            print(f"[TARGET] WARN: Check if transactions have valid posted_date with year matching active_years={active_years}")
    except Exception:
        pass

    def _process_target(target_sid: str, txns_for_target: List[dict], ignore_posted: bool = False) -> Dict[str, object]:
        def _infer_target_year(items: List[dict]) -> Optional[int]:
            years: Set[int] = set()
            for it in items:
                dt = str(it.get("posted_date") or "").strip()
                if len(dt) >= 4 and dt[:4].isdigit():
                    try:
                        years.add(int(dt[:4]))
                    except Exception:
                        continue
            return list(years)[0] if len(years) == 1 else None

        def _build_year_dates(year: int) -> List[str]:
            # Build M/D/YY list for Jan 1 .. Dec 31 of that year.
            start = date(int(year), 1, 1)
            end = date(int(year), 12, 31)
            out: List[str] = []
            cur = start
            while cur <= end:
                out.append(_format_mdy_yy(cur))
                cur += timedelta(days=1)
            return out

        # Choose the correct date->row mapping for THIS target workbook.
        # - 2025 (legacy workbook): uses configured static_dates list.
        # - any other year: uses a fresh year-only list so 1/1/YY maps to first_row.
        target_year = _infer_target_year(txns_for_target)
        if target_year == 2025:
            # Ensure row mapping starts at first_row with 1/1/25 (row 20 by default).
            # This prevents an off-by-one when static_dates includes 12/31/24 at the top.
            target_dates = _build_year_dates(2025)
        elif target_year is not None:
            target_dates = _build_year_dates(int(target_year))
        else:
            # Fallback: preserve prior behavior (single global list)
            target_dates = list(static_dates) if isinstance(static_dates, list) else []
            if target_dates and not has_year_routing:
                target_dates = _extend_static_dates(cfg, target_dates)

        dates_to_row = _build_date_row_map(target_dates, header_row, first_row)
        if not dates_to_row:
            raise SystemExit("Static dates list is empty; populate config.intake_static_dates.dates with M/D/YY strings.")

        try:
            print(f"[TARGET] processing company={company_upper} target_spreadsheet_id={target_sid} target_year={target_year or '<unknown>'} items={len(txns_for_target)}")
        except Exception:
            pass

        # Build case-insensitive tab title resolver from TARGET spreadsheet metadata
        try:
            meta = google_api_execute(
                service.spreadsheets().get(spreadsheetId=target_sid, fields="sheets(properties(title))"),
                label="target:tabs_meta",
            )
            titles = [s.get("properties", {}).get("title", "") for s in meta.get("sheets", [])]
        except Exception:
            titles = []
        title_map = {_norm_tab_key(t): str(t) for t in titles if isinstance(t, str)}

        def _resolve_tab_title(name: str) -> str:
            try:
                key = _norm_tab_key(name)
                return title_map.get(key, str(name))
            except Exception:
                return str(name)

        # Collect per-transaction targets to resolve to exact cells
        pending_writes: List[Tuple[str, str, str, int, str, int, str, str]] = []  # (tab, header, date_key, amount_cents, src_tab, row_idx0, txn_uid, source_sid)
        # NOTE: We store the resolved target A1 range per source row so we only mark
        # rows as posted when their target cell is confirmed written (or already correct).
        success_rows: List[Tuple[str, str, int, str]] = []  # (source_sid, src_tab, row_idx0, target_a1)
        success_notes: List[Tuple[str, str, int, str, str]] = []  # (source_sid, src_tab, row_idx0, note, target_a1)
        skipped_rows: List[Tuple[str, str, int, str]] = []  # (source_sid, src_tab, row_idx0, reason)
        skipped_tab_not_found: List[str] = []
        skipped_header_date: int = 0
        append_rows: List[List[object]] = []
        credit_cards_rows: List[Tuple[str, str, int]] = []  # (source_sid, src_tab, row_idx0)
        processed_txn_uids: Set[str] = set()
        skipped_txn_uids_no_rule: Set[str] = set()
        tabs_touched: Set[str] = set()
        
        # Diagnostic counters
        total_txns = len(txns_for_target)
        skipped_posted = 0
        skipped_wrong_company = 0
        
        # Pre-check: if most transactions are marked as posted (>90%), auto-enable reprocessing
        # This handles cases where transactions were incorrectly marked as posted
        if not ignore_posted and total_txns > 0:
            posted_count = sum(1 for t in txns_for_target if bool(t.get("posted_flag")))
            posted_pct = (posted_count / total_txns * 100) if total_txns > 0 else 0
            if posted_pct >= 90.0:
                print(f"[DIAG] {posted_count}/{total_txns} ({posted_pct:.1f}%) transactions are marked as posted. Auto-enabling reprocess mode...")
                ignore_posted = True

        for t in txns_for_target:
            company_id = (t.get("company_id") or "").strip().upper()
            source_tab = str(t.get("source_tab") or "").strip()
            source_sid = str(t.get("source_spreadsheet_id") or "").strip()
            row_idx = t.get("row_index_0based", 0)

            # Skip rows already posted (column F TRUE on source sheet)
            # IMPORTANT: If user clears Column F (Posted) or Column G (Notes), the CSV checksum changes,
            # triggering a re-run. Rows with Column F = empty/FALSE will be reprocessed here.
            # Can be overridden with KYLO_IGNORE_POSTED_FLAG=1 or KYLO_REPROCESS_POSTED=1
            if not ignore_posted and bool(t.get("posted_flag")):
                skipped_posted += 1
                continue
            if company_id != company_upper:
                skipped_wrong_company += 1
                continue

            try:
                if str(t.get("source_tab", "")).strip().lower() == "credit cards":
                    credit_cards_rows.append((source_sid, str(t.get("source_tab") or "CREDIT CARDS"), int(t.get("row_index_0based") or 0)))
            except Exception:
                pass

            src = t.get("description") or ""
            src_trim = src.strip()
            try:
                amount_cents = int(t.get("amount_cents", 0))
            except Exception:
                amount_cents = int(round(float(t.get("amount_cents") or 0)))
            amt = amount_cents / 100.0
            dt = t.get("posted_date")  # YYYY-MM-DD
            if dt:
                try:
                    y, m, d = str(dt).split("-")
                    yy = int(y) % 100
                    mm = int(m)
                    dd = int(d)
                    date_key = f"{mm}/{dd}/{yy:02d}"
                except Exception:
                    date_key = ""
            else:
                date_key = ""
            append_rows.append([date_key, company_id, src, amt])

            txn_uid = str(t.get("txn_uid") or "").strip()
            if not txn_uid:
                txn_uid = f"LEGACY|{company_upper}|{t.get('source_tab') or 'TRANSACTIONS'}|{int(t.get('row_index_0based') or 0)}|{amount_cents}"
            processed_txn_uids.add(txn_uid)

            # Matching policy per company
            rule = None
            if company_upper in relaxed_companies:
                best = None
                best_len = -1
                for r in approved_rules:
                    s = _normalize_text((r.source or "").strip())
                    if not s:
                        continue
                    if s.lower() in _normalize_text(src_trim).lower() and len(s) > best_len:
                        best = r
                        best_len = len(s)
                rule = best or rules_by_trim.get(src_trim) or rules.get(src)
            else:
                rule = rules_by_trim.get(src_trim) or rules_by_trim_upper.get(src_trim.upper()) or rules.get(src)

            if rule and rule.company_id:
                rule_company_upper = rule.company_id.strip().upper()
                if rule_company_upper and rule_company_upper != company_upper:
                    rule = None
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule company_id '{rule_company_upper}' doesn't match '{company_upper}'"))
                    skipped_txn_uids_no_rule.add(txn_uid)

            if not rule:
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"No rule match for: '{src_trim[:50]}'"))
                skipped_txn_uids_no_rule.add(txn_uid)
                continue
            if not rule.approved:
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule found but not approved: '{src_trim[:50]}'"))
                skipped_txn_uids_no_rule.add(txn_uid)
                continue
            if not rule.target_sheet:
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule approved but missing target_sheet: '{src_trim[:50]}'"))
                skipped_txn_uids_no_rule.add(txn_uid)
                continue
            if not rule.target_header:
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule approved but missing target_header: '{src_trim[:50]}'"))
                skipped_txn_uids_no_rule.add(txn_uid)
                continue
            if not date_key:
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), "Date not available"))
                continue

            resolved_tab = title_map.get(_norm_tab_key(str(rule.target_sheet)))
            if not resolved_tab:
                skipped_tab_not_found.append(str(rule.target_sheet))
                skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Target tab not found: {rule.target_sheet}"))
                continue

            pending_writes.append((resolved_tab, rule.target_header, date_key, int(amount_cents), source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), txn_uid, source_sid))

        # Print diagnostic summary
        print(f"[DIAG] Total transactions: {total_txns}")
        print(f"[DIAG] Skipped (already posted): {skipped_posted}")
        print(f"[DIAG] Skipped (wrong company): {skipped_wrong_company}")
        print(f"[DIAG] Processed for matching: {total_txns - skipped_posted - skipped_wrong_company}")
        print(f"[DIAG] Matched to rules: {len(pending_writes)}")
        
        # Auto-reprocess if all transactions are marked as posted but nothing matched
        # This handles the case where transactions were incorrectly marked as posted
        if not ignore_posted and skipped_posted > 0 and len(pending_writes) == 0 and (total_txns - skipped_wrong_company) == skipped_posted:
            print(f"[DIAG] WARN: All {skipped_posted} transactions are marked as posted but none matched rules.")
            print(f"[DIAG] Auto-enabling reprocess mode to check if posting actually occurred...")
            ignore_posted = True
            # Re-process with ignore_posted enabled
            skipped_posted = 0
            pending_writes = []
            skipped_rows = []
            skipped_tab_not_found = []
            skipped_txn_uids_no_rule = set()
            
            for t in txns_for_target:
                company_id = (t.get("company_id") or "").strip().upper()
                source_tab = str(t.get("source_tab") or "").strip()
                source_sid = str(t.get("source_spreadsheet_id") or "").strip()
                row_idx = t.get("row_index_0based", 0)
                
                if company_id != company_upper:
                    continue
                
                src = t.get("description") or ""
                src_trim = src.strip()
                try:
                    amount_cents = int(t.get("amount_cents", 0))
                except Exception:
                    amount_cents = int(round(float(t.get("amount_cents") or 0)))
                dt = t.get("posted_date")
                if dt:
                    try:
                        y, m, d = str(dt).split("-")
                        yy = int(y) % 100
                        mm = int(m)
                        dd = int(d)
                        date_key = f"{mm}/{dd}/{yy:02d}"
                    except Exception:
                        date_key = ""
                else:
                    date_key = ""
                
                txn_uid = str(t.get("txn_uid") or "").strip()
                if not txn_uid:
                    txn_uid = f"LEGACY|{company_upper}|{t.get('source_tab') or 'TRANSACTIONS'}|{int(t.get('row_index_0based') or 0)}|{amount_cents}"
                
                rule = None
                if company_upper in relaxed_companies:
                    best = None
                    best_len = -1
                    for r in approved_rules:
                        s = _normalize_text((r.source or "").strip())
                        if not s:
                            continue
                        if s.lower() in _normalize_text(src_trim).lower() and len(s) > best_len:
                            best = r
                            best_len = len(s)
                    rule = best or rules_by_trim.get(src_trim) or rules.get(src)
                else:
                    rule = rules_by_trim.get(src_trim) or rules_by_trim_upper.get(src_trim.upper()) or rules.get(src)
                
                if rule and rule.company_id:
                    rule_company_upper = rule.company_id.strip().upper()
                    if rule_company_upper and rule_company_upper != company_upper:
                        rule = None
                        skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule company_id '{rule_company_upper}' doesn't match '{company_upper}'"))
                        skipped_txn_uids_no_rule.add(txn_uid)
                
                if not rule:
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"No rule match for: '{src_trim[:50]}'"))
                    skipped_txn_uids_no_rule.add(txn_uid)
                    continue
                if not rule.approved:
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule found but not approved: '{src_trim[:50]}'"))
                    skipped_txn_uids_no_rule.add(txn_uid)
                    continue
                if not rule.target_sheet:
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule approved but missing target_sheet: '{src_trim[:50]}'"))
                    skipped_txn_uids_no_rule.add(txn_uid)
                    continue
                if not rule.target_header:
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Rule approved but missing target_header: '{src_trim[:50]}'"))
                    skipped_txn_uids_no_rule.add(txn_uid)
                    continue
                if not date_key:
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), "Date not available"))
                    continue
                
                resolved_tab = title_map.get(_norm_tab_key(str(rule.target_sheet)))
                if not resolved_tab:
                    skipped_tab_not_found.append(str(rule.target_sheet))
                    skipped_rows.append((source_sid, source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), f"Target tab not found: {rule.target_sheet}"))
                    continue
                
                pending_writes.append((resolved_tab, rule.target_header, date_key, int(amount_cents), source_tab or "TRANSACTIONS", int(t.get("row_index_0based") or 0), txn_uid, source_sid))
            
            print(f"[DIAG] After reprocess: {len(pending_writes)} transactions matched to rules")
        
        if skipped_txn_uids_no_rule:
            print(f"[RULES] WARN: {len(skipped_txn_uids_no_rule)} transactions did not match any rules for {company_upper}")
        if skipped_tab_not_found:
            print(f"[RULES] WARN: {len(set(skipped_tab_not_found))} unique target tabs not found: {', '.join(set(skipped_tab_not_found))}")

        # Resolve writes to exact A1 cells
        data: List[Dict[str, object]] = []
        unique_tabs = sorted({tab for (tab, _header, _date, _amt, _src_tab, _row0, _txn, _sid) in pending_writes})
        headers_map = _batch_read_headers(service, target_sid, unique_tabs, header_row)
        cell_totals: Dict[str, int] = {}
        cell_txns: Dict[str, Set[str]] = defaultdict(set)
        cell_source_tabs: Dict[str, Set[str]] = defaultdict(set)
        cell_meta: Dict[str, Tuple[str, str, str]] = {}
        # Cache of actual date labels in Column A for each tab (normalized m/d/yy -> row)
        date_map_cache: Dict[str, Dict[str, int]] = {}

        def _canonical_mdy(value: str) -> str:
            """Normalize common date label formats to M/D/YY (no leading zeros)."""
            s = _normalize_text(value)
            if not s:
                return ""
            # Accept M/D/YY or MM/DD/YY
            m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2,4})\s*$", s)
            if m:
                mm = int(m.group(1))
                dd = int(m.group(2))
                yy_raw = int(m.group(3))
                yy = yy_raw % 100  # tolerate YYYY
                return f"{mm}/{dd}/{yy:02d}"
            # Accept YYYY-MM-DD
            m2 = re.match(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$", s)
            if m2:
                mm = int(m2.group(2))
                dd = int(m2.group(3))
                yy = int(m2.group(1)) % 100
                return f"{mm}/{dd}/{yy:02d}"
            return s

        def _build_tab_date_map(tab: str) -> Dict[str, int]:
            """Read Column A date labels for a tab and build a normalized lookup."""
            if tab in date_map_cache:
                return date_map_cache[tab]
            qt = _quote_tab_a1(tab)
            # Read enough rows to cover a full year block (plus buffer)
            rng = f"{qt}!A{first_row}:A{first_row + 400}"
            res = google_api_execute(
                service.spreadsheets().values().get(
                    spreadsheetId=target_sid,
                    range=rng,
                    valueRenderOption="FORMATTED_VALUE",
                ),
                label="target:date_col_read",
            )
            vals = res.get("values", [])
            m: Dict[str, int] = {}
            for i, r in enumerate(vals):
                if not r:
                    continue
                key = _canonical_mdy(str(r[0] if r else ""))
                if not key:
                    continue
                # First occurrence wins
                if key not in m:
                    m[key] = first_row + i
            date_map_cache[tab] = m
            return m

        def _resolve_date_row(tab: str, date_key: str, static_row: Optional[int]) -> Optional[int]:
            """Resolve the correct row for a date, correcting off-by-one shifts using Column A."""
            want = _canonical_mdy(date_key)
            if not want:
                return static_row
            # Always build map lazily; it makes date mapping resilient to sheet edits/row inserts.
            try:
                tab_map = _build_tab_date_map(tab)
                actual = tab_map.get(want)
            except Exception:
                actual = None
            if static_row is None:
                return actual
            # If we have both, prefer the actual Column A match (prevents date shifts)
            if actual is not None and actual != static_row:
                try:
                    print(f"[DATE MAP] tab={tab} date={want} static_row={static_row} actual_row={actual} (correcting)")
                except Exception:
                    pass
                return actual
            return static_row

        for (tab, header, date_key, amount_cents, src_tab, row0, txn_uid, source_sid) in pending_writes:
            headers = headers_map.get(tab) or []
            norm = [str(h).strip().lower() for h in headers]
            wanted = (header or "").strip().lower()
            col_index = norm.index(wanted) if wanted in norm else -1
            if col_index < 0 and company_upper in relaxed_companies:
                for i, h in enumerate(norm):
                    if wanted and wanted in h:
                        col_index = i
                        break
            if col_index < 0:
                skipped_header_date += 1
                skipped_rows.append((source_sid, src_tab, row0, f"Header not found: {header}"))
                continue
            col_a1 = _col_to_a1(col_index)
            # Resolve date row with static mapping, then correct using Column A lookup.
            row_index = _resolve_date_row(tab, date_key, dates_to_row.get(date_key))
            if row_index is None:
                skipped_header_date += 1
                skipped_rows.append((source_sid, src_tab, row0, f"Date not found: {date_key}"))
                continue

            a1 = f"{_quote_tab_a1(tab)}!{col_a1}{row_index}"
            cell_totals[a1] = cell_totals.get(a1, 0) + int(amount_cents)
            if txn_uid:
                cell_txns[a1].add(txn_uid)
            if src_tab:
                cell_source_tabs[a1].add(str(src_tab).strip() or "TRANSACTIONS")
            else:
                cell_source_tabs[a1].add("TRANSACTIONS")
            cell_meta[a1] = (tab, header, date_key)
            tabs_touched.add(tab)
            success_rows.append((source_sid, src_tab, row0, a1))
            try:
                note_msg = f"Posted {amount_cents / 100.0:.2f} -> {tab}/{header} {date_key}"
            except Exception:
                note_msg = "Posted"
            success_notes.append((source_sid, src_tab, row0, note_msg, a1))

        updated_ranges: Set[str] = set()
        update_entries: List[Dict[str, object]] = []
        skipped_for_verify: List[Dict[str, object]] = []
        for a1, total_cents in cell_totals.items():
            tab, header, date_key = cell_meta.get(a1, ("", "", ""))
            txn_ids = cell_txns.get(a1, set())
            cell_key = compute_cell_key(tab, header, date_key, spreadsheet_id=target_sid)
            signature = compute_signature(txn_ids, total_cents)
            expected_value = round(total_cents / 100.0, 2)
            existing_signature = state.get_signature(company_upper, cell_key)
            if baseline_flag or existing_signature != signature:
                data.append({"range": a1, "values": [[expected_value]]})
                updated_ranges.add(a1)
                update_entries.append({"cell_key": cell_key, "signature": signature, "total_cents": total_cents, "range": a1})
            else:
                skipped_for_verify.append({"range": a1, "value": expected_value, "value_cents": total_cents, "cell_key": cell_key, "signature": signature, "txn_ids": txn_ids})

        def _parse_sheet_number(values: List[List[object]]) -> Optional[float]:
            if not values:
                return None
            row = values[0] if values[0] else []
            if not row:
                return None
            raw = row[0]
            if raw in ("", None):
                return None
            try:
                return float(str(raw).replace(",", ""))
            except Exception:
                return None

        if verify_flag and skipped_for_verify and service is not None:
            ranges_to_check = [item["range"] for item in skipped_for_verify if item["range"] not in updated_ranges]
            if ranges_to_check:
                verify_resp = google_api_execute(
                    service.spreadsheets()
                    .values()
                    .batchGet(
                        spreadsheetId=target_sid,
                        ranges=ranges_to_check,
                        valueRenderOption="UNFORMATTED_VALUE",
                    ),
                    label="target:verify_batchGet",
                )
                value_map: Dict[str, List[List[object]]] = {}
                for vr in verify_resp.get("valueRanges", []):
                    value_map[vr.get("range", "")] = vr.get("values", [])
                for item in skipped_for_verify:
                    rng = item["range"]
                    if rng in updated_ranges:
                        continue
                    current = _parse_sheet_number(value_map.get(rng, []))
                    expected = item["value"]
                    needs_update = current is None or abs(current - expected) > 0.005
                    if needs_update:
                        data.append({"range": rng, "values": [[expected]]})
                        updated_ranges.add(rng)
                        update_entries.append(
                            {
                                "cell_key": item["cell_key"],
                                "signature": item["signature"],
                                "total_cents": item["value_cents"],
                                "range": rng,
                            }
                        )

        read_only_env = os.environ.get("KYLO_READ_ONLY", "").strip().lower() in ("1", "true", "yes", "y")
        dry_env = os.environ.get("KYLO_SHEETS_DRY_RUN", "false").lower() in ("1", "true", "yes", "y")
        dry_cfg = bool(cfg.get("runtime.dry_run", False)) or not bool(cfg.get("posting.sheets.apply", False))
        dry_run = read_only_env or dry_env or dry_cfg
        try:
            apply_flag = bool(cfg.get("posting.sheets.apply", False))
            runtime_dry = bool(cfg.get("runtime.dry_run", False))
            env_raw = (os.environ.get("KYLO_SHEETS_DRY_RUN") or "").strip()
            ro_raw = (os.environ.get("KYLO_READ_ONLY") or "").strip()
            print(
                "[POSTING] "
                f"dry_run={dry_run} "
                f"(posting.sheets.apply={apply_flag}, runtime.dry_run={runtime_dry}, "
                f"KYLO_SHEETS_DRY_RUN='{env_raw or '<unset>'}', KYLO_READ_ONLY='{ro_raw or '<unset>'}')"
            )
            if dry_run:
                reasons = []
                if read_only_env:
                    reasons.append("env:KYLO_READ_ONLY")
                if dry_env:
                    reasons.append("env:KYLO_SHEETS_DRY_RUN")
                if runtime_dry:
                    reasons.append("config:runtime.dry_run")
                if not apply_flag:
                    reasons.append("config:posting.sheets.apply=false")
                if reasons:
                    print(f"[POSTING] Writes DISABLED due to: {', '.join(reasons)}")
        except Exception:
            # Never fail a run due to logging
            pass

        cells_written = 0
        rows_marked_true = 0
        # Track which target ranges were actually written this run (to avoid falsely marking source rows as posted).
        ranges_attempted: Set[str] = set()
        ranges_written: Set[str] = set()
        failed_ranges: Set[str] = set()
        if data:
            try:
                ranges_attempted = {str(it.get("range", "")) for it in data if it.get("range")}
            except Exception:
                ranges_attempted = set()
            if dry_run:
                cells_written = len(data)
                # Capture the write plan for auditing ("what would have been written").
                try:
                    for it in data:
                        rng = str(it.get("range", ""))
                        vals = it.get("values", [])
                        v0 = None
                        try:
                            v0 = vals[0][0] if vals and isinstance(vals, list) and vals[0] else None
                        except Exception:
                            v0 = None
                        if rng:
                            write_plan.append(
                                {
                                    "target_spreadsheet_id": str(target_sid),
                                    "range": rng,
                                    "value": v0,
                                    "source_tabs": sorted(list(cell_source_tabs.get(rng, set()))),
                                }
                            )
                except Exception:
                    pass
            else:
                remaining_data = data[:]
                max_retries = len(data)
                retry_count = 0
                protected_cells: List[str] = []
                while remaining_data and retry_count < max_retries:
                    retry_count += 1
                    try:
                        google_api_execute(
                            service.spreadsheets().values().batchUpdate(
                                spreadsheetId=target_sid,
                                body={"valueInputOption": "RAW", "data": remaining_data},
                            ),
                            label="target:batchUpdate_values",
                        )
                        cells_written = len(remaining_data)
                        try:
                            ranges_written = {str(it.get("range", "")) for it in remaining_data if it.get("range")}
                        except Exception:
                            ranges_written = set()
                        break
                    except HttpError as e:
                        error_content = str(e.content) if hasattr(e, "content") else str(e)
                        try:
                            status = getattr(e, "status_code", None)
                        except Exception:
                            status = None
                        print(f"[ERROR] Sheets batchUpdate failed (status={status}): {error_content}")
                        match = re.search(r"Invalid data\\[(\\d+)\\]", error_content)
                        if match:
                            protected_index = int(match.group(1))
                            if protected_index < len(remaining_data):
                                protected_range = remaining_data[protected_index].get("range", "unknown")
                                protected_cells.append(str(protected_range))
                                remaining_data.pop(protected_index)
                                continue
                        break
                if protected_cells:
                    print(f"[WARN] {len(protected_cells)} protected cells skipped in target={target_sid}")
                    failed_ranges |= set(protected_cells)
        else:
            # No updates needed; treat all resolved ranges as OK without writing.
            ranges_attempted = set()

        # Ranges that were resolved to a target cell and either:
        # - did not require updating (signature match), OR
        # - were successfully written this run.
        all_resolved_ranges = set(cell_totals.keys())
        ranges_ok_without_write = all_resolved_ranges - ranges_attempted
        # IMPORTANT:
        # Historically we treated "signature match" as equivalent to "cell is correct" and would
        # mark the source row as posted. In practice the sheet can drift (manual edits, overwrites,
        # protected ranges, partial failures), so we must *verify* any range we did not write
        # before marking source rows as posted/processed.
        ranges_verified_ok: Set[str] = set()
        ranges_verified_bad: Set[str] = set()
        try:
            # Only spend API calls when we might mark posted, and we have ranges that were not written.
            mark_posted_enabled = bool(cfg.get("posting.mark_posted", True))
            if (not dry_run) and mark_posted_enabled and ranges_ok_without_write:
                print(f"[VERIFY] Checking {len(ranges_ok_without_write)} ranges that matched signatures (not written)")
                verify_resp = google_api_execute(
                    service.spreadsheets()
                    .values()
                    .batchGet(
                        spreadsheetId=target_sid,
                        ranges=sorted(ranges_ok_without_write),
                        valueRenderOption="UNFORMATTED_VALUE",
                    ),
                    label="target:verify_posted_ok_ranges",
                )
                value_map: Dict[str, List[List[object]]] = {}
                for vr in verify_resp.get("valueRanges", []):
                    value_map[str(vr.get("range", ""))] = vr.get("values", [])
                for rng in ranges_ok_without_write:
                    # Expect the exact computed total for this range
                    total_cents = cell_totals.get(rng)
                    if total_cents is None:
                        ranges_verified_bad.add(rng)
                        continue
                    expected = round(int(total_cents) / 100.0, 2)
                    current = _parse_sheet_number(value_map.get(rng, []))
                    if current is not None and abs(float(current) - float(expected)) <= 0.005:
                        ranges_verified_ok.add(rng)
                    else:
                        ranges_verified_bad.add(rng)
                print(f"[VERIFY] Verified {len(ranges_verified_ok)} ranges OK, {len(ranges_verified_bad)} ranges BAD")
            elif not mark_posted_enabled:
                print(f"[VERIFY] Skipped - posting.mark_posted={mark_posted_enabled}")
            elif not ranges_ok_without_write:
                print(f"[VERIFY] Skipped - no ranges to verify (all ranges were written or empty)")
        except Exception as e:
            # If verification fails for any reason, be conservative and do not mark unwritten ranges as posted.
            print(f"[VERIFY] Verification failed: {e}")
            ranges_verified_ok = set()
            ranges_verified_bad = set(ranges_ok_without_write)

        # If a user unchecks Column F, ingestion sheet is the source of truth:
        # we should re-post any target cell that is *not* correct, even if our local signature
        # state claimed it was already posted.
        repair_written: Set[str] = set()
        if (not dry_run) and ranges_verified_bad:
            repair_data: List[Dict[str, object]] = []
            for rng in sorted(ranges_verified_bad):
                total_cents = cell_totals.get(rng)
                if total_cents is None:
                    continue
                expected = round(int(total_cents) / 100.0, 2)
                repair_data.append({"range": rng, "values": [[expected]]})
            if repair_data:
                try:
                    google_api_execute(
                        service.spreadsheets().values().batchUpdate(
                            spreadsheetId=target_sid,
                            body={"valueInputOption": "RAW", "data": repair_data},
                        ),
                        label="target:repair_batchUpdate",
                    )
                    repair_written = {str(it.get("range", "")) for it in repair_data if it.get("range")}
                except HttpError as e:
                    error_content = str(e.content) if hasattr(e, "content") else str(e)
                    print(f"[ERROR] Sheets repair batchUpdate failed: {error_content}")
                    repair_written = set()
                except Exception as e:
                    print(f"[ERROR] Sheets repair batchUpdate failed: {e}")
                    repair_written = set()

        # Treat repaired ranges as written/ok.
        if repair_written:
            ranges_written |= repair_written
            ranges_verified_ok |= repair_written
            ranges_verified_bad -= repair_written

        posted_ok_ranges = ranges_written | ranges_verified_ok
        print(f"[POST] Summary: {len(ranges_written)} written, {len(ranges_verified_ok)} verified OK, {len(all_resolved_ranges)} total resolved")

        # If we attempted a range but did not write it, treat it as failed.
        failed_ranges |= (ranges_attempted - ranges_written)
        # If we did not write a range and verification shows it is NOT correct, treat as failed for marking/state.
        failed_ranges |= ranges_verified_bad
        if failed_ranges:
            print(
                f"[WARN] {len(failed_ranges)} target ranges were NOT written; "
                "source rows for those targets will NOT be marked posted."
            )

        if not dry_run and (update_entries or processed_txn_uids or skipped_txn_uids_no_rule):
            try:
                # Only persist "processed" txns that we know are reflected in the target:
                # either the target cell was written, or it was already correct (signature match).
                processed_ok: Set[str] = set()
                for rng in posted_ok_ranges:
                    processed_ok |= set(cell_txns.get(rng, set()) or set())
                state.merge_processed(company_upper, processed_ok)
                if skipped_txn_uids_no_rule:
                    state.add_skipped(company_upper, skipped_txn_uids_no_rule)
                for entry in update_entries:
                    rng = str(entry.get("range") or "")
                    if rng and rng in ranges_written:
                        state.set_signature(company_upper, str(entry["cell_key"]), str(entry["signature"]))
                save_state(state)
            except StateError as exc:
                print(f"[WARN] unable to persist posting state: {exc}")

        if not dry_run and bool(cfg.get("posting.mark_posted", True)):
            mark_by_sid: Dict[str, List[Dict[str, object]]] = defaultdict(list)
            note_by_sid: Dict[str, List[Dict[str, object]]] = defaultdict(list)
            # Resolve "processed" + "notes" columns per (spreadsheet_id, tab) from header row.
            col_cache: Dict[Tuple[str, str], Tuple[str, str]] = {}

            def _resolve_mark_and_note_cols(sid: str, tab: str) -> Tuple[str, str]:
                key = (sid, tab)
                if key in col_cache:
                    return col_cache[key]
                # Default to F/G
                processed_col = "F"
                notes_col = "G"
                try:
                    headers = _read_header_row(service, sid, tab, header_row=1)
                    # Prefer explicit "Processed" / "Posted" column names for the checkbox.
                    idx = _find_header_col(headers, ["processed", "posted"])
                    if idx is not None:
                        processed_col = _a1_col(idx)
                    # Prefer an explicit notes column if present (otherwise fallback to G).
                    nidx = _find_header_col(headers, ["notes", "match_notes", "match notes"])
                    if nidx is not None:
                        notes_col = _a1_col(nidx)
                except Exception:
                    pass
                col_cache[key] = (processed_col, notes_col)
                return processed_col, notes_col

            for (source_sid, src_tab, row0, target_a1) in success_rows:
                if target_a1 not in posted_ok_ranges:
                    continue
                try:
                    sheet_row = int(row0) + 1
                    a1_tab = _quote_tab_for_a1(src_tab)
                    pcol, _ncol = _resolve_mark_and_note_cols(source_sid, src_tab)
                    mark_by_sid[source_sid].append({"range": f"{a1_tab}!{pcol}{sheet_row}", "values": [[True]]})
                except Exception:
                    continue
            for (source_sid, src_tab, row0, msg, target_a1) in success_notes:
                if target_a1 not in posted_ok_ranges:
                    continue
                try:
                    sheet_row = int(row0) + 1
                    a1_tab = _quote_tab_for_a1(src_tab)
                    _pcol, ncol = _resolve_mark_and_note_cols(source_sid, src_tab)
                    note_by_sid[source_sid].append({"range": f"{a1_tab}!{ncol}{sheet_row}", "values": [[str(msg)]]})
                except Exception:
                    continue
            for (source_sid, src_tab, row0, reason) in skipped_rows:
                try:
                    sheet_row = int(row0) + 1
                    a1_tab = _quote_tab_for_a1(src_tab)
                    _pcol, ncol = _resolve_mark_and_note_cols(source_sid, src_tab)
                    note_by_sid[source_sid].append({"range": f"{a1_tab}!{ncol}{sheet_row}", "values": [[f"Skip: {str(reason)}"]]})
                except Exception:
                    continue
            for (source_sid, src_tab, row0) in credit_cards_rows:
                try:
                    sheet_row = int(row0) + 1
                    a1_tab = _quote_tab_for_a1(src_tab)
                    _pcol, ncol = _resolve_mark_and_note_cols(source_sid, src_tab)
                    note_by_sid[source_sid].append({"range": f"{a1_tab}!{ncol}{sheet_row}", "values": [["Processed"]]})
                except Exception:
                    continue

            for sid, mark_data in mark_by_sid.items():
                if not sid or not mark_data:
                    continue
                try:
                    print(f"[MARK] Marking {len(mark_data)} rows as posted in spreadsheet {sid[:20]}...")
                    google_api_execute(
                        service.spreadsheets().values().batchUpdate(
                            spreadsheetId=sid,
                            body={"valueInputOption": "USER_ENTERED", "data": mark_data},
                        ),
                        label="source:mark_posted_batch",
                    )
                    rows_marked_true += len(mark_data)
                    print(f"[MARK] Successfully marked {len(mark_data)} rows as posted")
                except HttpError:
                    pass
            for sid, note_data in note_by_sid.items():
                if not sid or not note_data:
                    continue
                try:
                    print(f"[NOTES] Writing {len(note_data)} notes to spreadsheet {sid[:20]}...")
                    google_api_execute(
                        service.spreadsheets().values().batchUpdate(
                            spreadsheetId=sid,
                            body={"valueInputOption": "USER_ENTERED", "data": note_data},
                        ),
                        label="source:notes_batch",
                    )
                    print(f"[NOTES] Successfully wrote {len(note_data)} notes")
                except HttpError:
                    pass

        if not dry_run and bool(cfg.get("posting.append_transactions", False)):
            _ensure_transactions_append(service, target_sid, append_rows)

        return {
            "target_sid": target_sid,
            "cells_written": int(cells_written),
            "rows_marked_true": int(rows_marked_true),
            "tabs": sorted(tabs_touched),
            "skipped_tab_not_found": skipped_tab_not_found,
            "skipped_header_date": int(skipped_header_date),
            "skipped_rows": skipped_rows,
        }

    # Execute per-target posting and aggregate
    total_cells_written = 0
    total_rows_marked_true = 0
    tabs_all: Set[str] = set()
    skipped_tab_not_found_all: List[str] = []
    skipped_header_date_total = 0
    skipped_rows_all: List[Tuple[str, str, int, str]] = []

    for target_sid, txns_for_target in txns_by_target_sid.items():
        result = _process_target(target_sid, txns_for_target, ignore_posted=ignore_posted_flag)
        total_cells_written += int(result.get("cells_written", 0))
        total_rows_marked_true += int(result.get("rows_marked_true", 0))
        tabs_all |= set(result.get("tabs", []))
        skipped_tab_not_found_all.extend(list(result.get("skipped_tab_not_found", [])))
        skipped_header_date_total += int(result.get("skipped_header_date", 0))
        skipped_rows_all.extend(list(result.get("skipped_rows", [])))

    # Basic diagnostics for skipped items (printed once per run)
    if skipped_tab_not_found_all:
        unique = sorted(set(skipped_tab_not_found_all))
        print(f"[SKIP] target sheet not found for rules: {unique[:10]}{' ...' if len(unique)>10 else ''}")
    if skipped_header_date_total:
        print(f"[SKIP] {skipped_header_date_total} items skipped due to missing header or date row")
    if skipped_rows_all:
        skipped_by_reason: Dict[str, int] = defaultdict(int)
        for _sid, _src_tab, _row0, reason in skipped_rows_all:
            skipped_by_reason[reason] += 1
        if skipped_by_reason:
            print(f"[SKIP] Transaction skip summary:")
            for reason, count in sorted(skipped_by_reason.items()):
                print(f"  - {reason}: {count} transactions")

    # Return a small summary for watchers/diagnostics
    # Optionally write the dry-run write plan to disk.
    wp = (os.environ.get("KYLO_WRITE_PLAN_PATH") or "").strip()
    wp_out = None
    if wp and write_plan:
        try:
            p = Path(wp)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Stable ordering for diffs
            write_plan_sorted = sorted(write_plan, key=lambda x: (x.get("target_spreadsheet_id", ""), x.get("range", "")))
            p.write_text(json.dumps(write_plan_sorted, indent=2), encoding="utf-8")
            wp_out = str(p)
            print(f"[DRY RUN] write plan saved: {wp_out} ({len(write_plan_sorted)} writes)")
        except Exception as e:
            print(f"[DRY RUN] failed to write write plan: {e}")

    # Summarize write/mark candidates by source tab (TRANSACTIONS vs BANK, etc.)
    try:
        postable_rows_by_tab: Dict[str, Set[str]] = defaultdict(set)
        for (sid, src_tab, row0, a1) in success_rows_all:
            t = (str(src_tab).strip() or "TRANSACTIONS").upper()
            postable_rows_by_tab[t].add(f"{sid}:{int(row0)}")
        postable_rows_counts = {k: len(v) for k, v in sorted(postable_rows_by_tab.items())}
    except Exception:
        postable_rows_counts = {}

    try:
        writes_by_tab: Dict[str, Set[str]] = defaultdict(set)
        for item in write_plan:
            rng = str(item.get("range", ""))
            for t in item.get("source_tabs") or []:
                writes_by_tab[str(t).strip().upper()].add(rng)
        write_counts_by_tab = {k: len(v) for k, v in sorted(writes_by_tab.items())}
    except Exception:
        write_counts_by_tab = {}

    return {
        "company": company,
        "cells_written": int(total_cells_written),
        "rows_marked_true": int(total_rows_marked_true),
        "tabs": sorted(tabs_all),
        "write_plan_path": wp_out,
        "write_plan_count": int(len(write_plan)),
        "postable_source_rows_by_tab": postable_rows_counts,
        "target_writes_by_source_tab": write_counts_by_tab,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Sort and post petty cash via JGDTruth rules (values only)")
    ap.add_argument("--company", required=True, help="Company key (NUGZ, 710, PUFFIN, JGD)")
    ap.add_argument("--baseline", action="store_true", help="Force full write and reseed incremental state")
    ap.add_argument(
        "--verify",
        dest="verify_flag",
        action="store_true",
        help="Read back unchanged cells to detect manual edits (overrides KYLO_VERIFY_POST)",
    )
    ap.add_argument(
        "--no-verify",
        dest="verify_flag",
        action="store_false",
        help="Disable verification even if KYLO_VERIFY_POST=1",
    )
    ap.add_argument(
        "--rules-changed",
        action="store_true",
        help="Clear skipped transactions and re-evaluate all transactions with updated rules",
    )
    ap.add_argument(
        "--reprocess-posted",
        action="store_true",
        help="Reprocess transactions even if Column F (Posted) is TRUE",
    )
    ap.set_defaults(verify_flag=None)
    args = ap.parse_args()
    if args.reprocess_posted:
        os.environ["KYLO_IGNORE_POSTED_FLAG"] = "1"
    ret = run(args.company, baseline=args.baseline, verify=args.verify_flag, rules_changed=args.rules_changed)
    # Print summary when run directly
    try:
        if isinstance(ret, dict):
            print(json.dumps(ret))  # type: ignore
            return 0
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


