from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except Exception:  # Python <3.9 fallback not expected in this scaffold
    ZoneInfo = None  # type: ignore


def _to_cell(value: Any) -> Dict[str, Any]:
    return {"userEnteredValue": {"stringValue": "" if value is None else str(value)}}


def _to_row(values: List[Any]) -> Dict[str, Any]:
    return {"values": [_to_cell(v) for v in values]}


CENTRAL_TZ = ZoneInfo("America/Chicago") if ZoneInfo else None


def _strip(val: Optional[str]) -> str:
    return (val or "").strip()


def parse_date(v: Any) -> Optional[str]:
    """Parse date from M/D/YY, M/D/YYYY, or Sheets serial. Return YYYY-MM-DD or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        # Assume Google Sheets serial (days since 1899-12-30)
        base = datetime(1899, 12, 30)
        try:
            return (base + timedelta(days=int(v))).strftime("%Y-%m-%d")
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    # Try common US formats
    for fmt in ["%m/%d/%y", "%m/%d/%Y", "%m/%-d/%y", "%m/%-d/%Y", "%-m/%-d/%y", "%-m/%-d/%Y"]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    # Fallback: try with single-digit tolerance without platform-specific %-m
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mm = int(m.group(1))
        dd = int(m.group(2))
        yy = int(m.group(3))
        if yy < 100:
            yy += 2000
        try:
            dt = datetime(yy, mm, dd)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def _parse_money_to_decimal(s: str) -> Optional[float]:
    # Accept formats like "$ 799.07" or "$ (300.00)"
    if not s:
        return None
    s = s.strip()
    # Remove dollar and spaces
    s = s.replace("$", "").replace(",", "").strip()
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    try:
        val = float(s)
        if negative:
            val = -val
        return round(val, 2)
    except Exception:
        return None


def normalize_amount_expr(v: Any) -> Optional[str]:
    if v is None:
        return None
    # treat numbers as already computed; strings parse via money helper
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"={float(v):.2f}"
    if isinstance(v, str):
        num = _parse_money_to_decimal(v)
        if num is None:
            return None
        return f"={num:.2f}"
    return None


def normalize_row(raw: Dict[str, Any], tab_company_id: str) -> Dict[str, Any]:
    return {
        "row_hash": _strip(raw.get("Row_Hash")),
        "date": parse_date(raw.get("Date")),
        # source normalized to lowercase for stable hashing regardless of user case
        "source": _strip(raw.get("Source")).lower(),
        "company_id": _strip(raw.get("Company_ID") or tab_company_id),
        "amount_expr": normalize_amount_expr(raw.get("Amount")),
        "target_sheet": _strip(raw.get("Target_Sheet")),
        "target_header": _strip(raw.get("Target_Header")),
        "match_notes": _strip(raw.get("Match_Notes")),
        "approved": str(raw.get("Approved")).strip().upper() == "TRUE",
        "rule_id": _strip(raw.get("Rule_ID")),
    }


def stable_hash(row_norm: Dict[str, Any]) -> str:
    payload = {
        k: row_norm.get(k)
        for k in [
            "date",
            "source",
            "company_id",
            "amount_expr",
            "target_sheet",
            "target_header",
            "match_notes",
        ]
    }
    return sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate_row(row_norm: Dict[str, Any], tab_company_id: str) -> List[Tuple[str, str]]:
    errors: List[Tuple[str, str]] = []
    if not row_norm.get("approved"):
        errors.append(("NOT_APPROVED", "Approved must be TRUE"))
    if row_norm.get("company_id") != tab_company_id:
        errors.append(("COMPANY_MISMATCH", f"Company must be {tab_company_id}"))
    if not row_norm.get("source"):
        errors.append(("SOURCE_EMPTY", "Source required"))
    if not row_norm.get("target_sheet"):
        errors.append(("TARGET_SHEET_EMPTY", "Target_Sheet required"))
    if not row_norm.get("target_header"):
        errors.append(("TARGET_HEADER_EMPTY", "Target_Header required"))
    # FUTURE_DATE warning (non-blocking)
    d = row_norm.get("date")
    if d:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            if CENTRAL_TZ is not None:
                today_central = datetime.now(CENTRAL_TZ).date()
            else:
                today_central = datetime.now().date()
            if dt > today_central:
                errors.append(("FUTURE_DATE", "Date is in the future"))
        except Exception:
            pass
    return errors


@dataclass
class PendingTab:
    sheet_id: int
    title: str
    rows: List[Dict[str, Any]]  # header-mapped rows


def list_company_pending_tabs(service, spreadsheet_id: str) -> List[Tuple[int, str]]:
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )
    out: List[Tuple[int, str]] = []
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        title = props.get("title", "")
        # Support both old and new naming conventions
        if title.startswith("Pending Rules – ") or title.endswith(" Pending"):
            out.append((int(props.get("sheetId")), title))
    return out


def batch_read_pending_values(service, spreadsheet_id: str, tabs: List[Tuple[int, str]]) -> List[PendingTab]:
    if not tabs:
        return []
    data_filters = [
        {
            "gridRange": {
                "sheetId": sid,
                "startRowIndex": 0,
                "startColumnIndex": 0,
                "endColumnIndex": 11,
            }
        }
        for (sid, _title) in tabs
    ]
    resp = (
        service.spreadsheets()
        .values()
        .batchGetByDataFilter(
            spreadsheetId=spreadsheet_id, body={"dataFilters": data_filters, "valueRenderOption": "UNFORMATTED_VALUE"}
        )
        .execute()
    )
    matched = resp.get("valueRanges", [])
    out: List[PendingTab] = []
    for (tab, vr) in zip(tabs, matched):
        values = vr.get("valueRange", {}).get("values", [])
        if not values:
            out.append(PendingTab(sheet_id=tab[0], title=tab[1], rows=[]))
            continue
        header = values[0]
        body = values[1:]
        rows: List[Dict[str, Any]] = []
        for r in body:
            row_map = {header[i]: (r[i] if i < len(r) else None) for i in range(len(header))}
            rows.append(row_map)
        out.append(PendingTab(sheet_id=tab[0], title=tab[1], rows=rows))
    return out


def _central_now_str() -> str:
    now = datetime.now(CENTRAL_TZ) if CENTRAL_TZ is not None else datetime.now()
    return now.strftime("%m/%d/%y %I:%M:%S %p")


def _extract_company_from_title(title: str) -> str:
    # Support both naming conventions:
    # "Pending Rules – 710" -> "710"
    # "710 Pending" -> "710"
    if title.startswith("Pending Rules – "):
        parts = title.split("–", 1)
        return parts[1].strip() if len(parts) == 2 else title
    elif title.endswith(" Pending"):
        return title[:-len(" Pending")].strip()
    else:
        return title


def build_write_processed_marks(processed_marks: List[Tuple[int, int, str, str]]) -> List[Dict[str, Any]]:
    """processed_marks: list of tuples (sheetId, rowIndex0, processed_at_str, row_hash)

    We must group by sheet and write contiguous blocks for columns J (index 10 -> Processed_At) and A (index 0 -> Row_Hash).
    But Row_Hash is also system-managed. We will write both A and K in one pass using two ranges per contiguous block.
    """
    if not processed_marks:
        return []
    # Group by sheet id
    by_sheet: Dict[int, List[Tuple[int, str, str]]] = {}
    for sid, row0, processed_at, row_hash in processed_marks:
        by_sheet.setdefault(sid, []).append((row0, processed_at, row_hash))
    requests: List[Dict[str, Any]] = []
    for sid, items in by_sheet.items():
        # Sort by row index
        items.sort(key=lambda x: x[0])
        # Coalesce into contiguous ranges
        block: List[Tuple[int, str, str]] = []
        start = None
        last = None
        def flush():
            nonlocal requests, block, start, last
            if not block:
                return
            # Write Processed_At (column K index 10) and Row_Hash (column A index 0)
            processed_rows = [(p, h) for (_r0, p, h) in block]
            # First Row_Hash (A)
            requests.append(
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sid,
                            "startRowIndex": start,
                            "endRowIndex": last + 1,
                            "startColumnIndex": 0,
                            "endColumnIndex": 1,
                        },
                        "fields": "userEnteredValue",
                        "rows": [_to_row([h]) for (_p, h) in [(p, h) for (p, h) in processed_rows]],
                    }
                }
            )
            # Then Processed_At (K)
            requests.append(
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sid,
                            "startRowIndex": start,
                            "endRowIndex": last + 1,
                            "startColumnIndex": 10,
                            "endColumnIndex": 11,
                        },
                        "fields": "userEnteredValue",
                        "rows": [_to_row([p]) for (p, _h) in processed_rows],
                    }
                }
            )
            block = []
            start = None
            last = None
        for row0, processed_at, row_hash in items:
            if start is None:
                start = row0
                last = row0
                block = [(row0, processed_at, row_hash)]
            elif row0 == last + 1:
                last = row0
                block.append((row0, processed_at, row_hash))
            else:
                flush()
                start = row0
                last = row0
                block = [(row0, processed_at, row_hash)]
        flush()
    return requests


def importer_run(service, db, spreadsheet_id: str) -> Dict[str, Any]:
    # 1) Discover tabs and batch read
    tabs = list_company_pending_tabs(service, spreadsheet_id)
    tab_data = batch_read_pending_values(service, spreadsheet_id, tabs)

    promotions: Dict[str, List[Tuple[Dict[str, Any], int, int, str]]] = {}
    processed_marks: List[Tuple[int, int, str, str]] = []

    # 2) Normalize, validate, dedupe
    for tab in tab_data:
        company = _extract_company_from_title(tab.title)
        for r_index, raw in enumerate(tab.rows, start=1):
            # rows start at 2 in UI, zero-index for API is 1 for the first body row
            ui_row_num = r_index + 1
            row0 = r_index  # zero-based for updateCells
            norm = normalize_row(raw, company)
            if not norm.get("approved"):
                continue
            errs = validate_row(norm, company)
            # Drop non-blocking FUTURE_DATE warnings for DB; could record elsewhere
            blocking = [e for e in errs if e[0] != "FUTURE_DATE"]
            if blocking:
                # skip invalid rows; could collect to errors sheet
                continue
            row_hash = stable_hash(norm)
            if db.rule_exists(company, norm["source"], row_hash):
                processed_marks.append((tab.sheet_id, row0, _central_now_str(), row_hash))
                continue
            promotions.setdefault(company, []).append((norm, tab.sheet_id, row0, row_hash))

    # 3) Promote per company
    touched: List[str] = []
    for company, items in promotions.items():
        if not items:
            continue
        with db.tx() as tx:
            prior = db.get_active_version(company, tx) or 0
            ruleset_id, version = db.insert_ruleset(company, prior + 1, tx)
            for norm, sid, row0, row_hash in items:
                db.insert_rule(
                    ruleset_id=ruleset_id,
                    company_id=company,
                    date=norm.get("date"),
                    source=norm.get("source"),
                    amount_expr=norm.get("amount_expr"),
                    target_sheet=norm.get("target_sheet"),
                    target_header=norm.get("target_header"),
                    match_notes=norm.get("match_notes"),
                    row_hash=row_hash,
                    tx=tx,
                )
                processed_marks.append((sid, row0, _central_now_str(), row_hash))
            if prior:
                db.retire_previous_ruleset(company, prior, tx)
            db.audit(company, "PROMOTE", ruleset_id, {"inserted": len(items)}, tx)
        touched.append(company)

    # 4) Build single batchUpdate
    requests: List[Dict[str, Any]] = []
    for company in touched:
        # Clear and write Active unique Sources
        # Resolve existing sheet ids directly via metadata to avoid external imports
        meta = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
            .execute()
        )
        titles_to_ids = {s.get("properties", {}).get("title"): int(s.get("properties", {}).get("sheetId")) for s in meta.get("sheets", [])}
        # Support both old and new naming conventions for Active tab
        active_id = titles_to_ids.get(f"Active Rules – {company}") or titles_to_ids.get(f"{company} Active")
        # Skip Active projection if missing
        if active_id is None:
            continue
        active_rows = db.fetch_active_sources_rows(company)
        # Clear active + write rows
        requests.extend(
            [
                {
                    "updateCells": {
                        "range": {"sheetId": active_id, "startRowIndex": 1},
                        "fields": "userEnteredValue",
                    }
                },
                {
                    "updateCells": {
                        "range": {"sheetId": active_id, "startRowIndex": 1, "startColumnIndex": 0},
                        "fields": "userEnteredValue",
                        "rows": [_to_row(row) for row in active_rows],
                    }
                },
            ]
        )

    requests.extend(build_write_processed_marks(processed_marks))

    if requests:
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute()

    # 5) Emit events (stub)
    for company in touched:
        publish_rules_updated(company, sources=[], version=db.get_active_version(company), effective_at=_central_now_str())

    return {"touched": touched, "processed_rows": len(processed_marks)}


def publish_rules_updated(company_id: str, sources: List[str], version: Optional[int], effective_at: str) -> None:
    # Stub for tests; in real system, send to message bus
    print(json.dumps({"company_id": company_id, "version": version, "effective_at": effective_at}))


