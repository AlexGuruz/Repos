"""
Layer 1: Load config and fetch from GrowFlow API and Google Sheets.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Config paths relative to company_bi/
_COMPANY_BI_ROOT = Path(__file__).resolve().parent.parent


def _load_yaml(name: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required: pip install pyyaml")
    path = _COMPANY_BI_ROOT / "config" / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_sources_config() -> dict[str, Any]:
    return _load_yaml("sources.yaml")


def load_categories_config() -> dict[str, Any]:
    return _load_yaml("categories.yaml")


def fetch_growflow_order_items(
    months_back: int = 24,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch all order items (SoldAt) for the last months_back months."""
    import sys
    growflow_root = _COMPANY_BI_ROOT.parent
    if str(growflow_root) not in sys.path:
        sys.path.insert(0, str(growflow_root))
    from lib.growflow_queries import (
        ORDER_ITEMS_QUERY,
        PAGE_SIZE,
        date_range_to_where,
        fetch_paginated,
    )
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=months_back * 31)
    from_iso = start.strftime("%Y-%m-%dT00:00:00.000Z")
    to_iso = now.strftime("%Y-%m-%dT23:59:59.999Z")
    where = date_range_to_where("SoldAt", from_iso, to_iso)
    return fetch_paginated(
        "findOrderItems",
        ORDER_ITEMS_QUERY,
        {"first": PAGE_SIZE, "where": where},
        credentials_path=credentials_path,
    )


def fetch_growflow_packages(
    months_back: int = 24,
    credentials_path: str | None = None,
    chunk_days: int = 180,
) -> list[dict[str, Any]]:
    """Fetch packages in chunks (createdAt) for inventory metrics."""
    import sys
    growflow_root = _COMPANY_BI_ROOT.parent
    if str(growflow_root) not in sys.path:
        sys.path.insert(0, str(growflow_root))
    from lib.growflow_queries import (
        PACKAGES_TABLE_QUERY,
        PAGE_SIZE,
        date_range_to_where,
        fetch_paginated,
    )
    now = datetime.now(timezone.utc)
    total_days = months_back * 31
    nodes: list[dict] = []
    seen: set[str] = set()
    chunk_start = now
    while total_days > 0:
        chunk_end = chunk_start - timedelta(days=min(chunk_days, total_days))
        from_iso = chunk_end.strftime("%Y-%m-%dT00:00:00.000Z")
        to_iso = chunk_start.strftime("%Y-%m-%dT23:59:59.999Z")
        where = date_range_to_where("createdAt", from_iso, to_iso)
        try:
            chunk = fetch_paginated(
                "findPackages",
                PACKAGES_TABLE_QUERY,
                {"first": PAGE_SIZE, "where": where},
                credentials_path=credentials_path,
            )
            for n in chunk:
                pid = n.get("objectId") or n.get("id") or ""
                if pid and pid not in seen:
                    seen.add(pid)
                    nodes.append(n)
        except Exception:
            break
        chunk_start = chunk_end
        total_days -= chunk_days
    return nodes


def fetch_sheets_transactions(
    spreadsheet_id: str,
    tab_names: list[str],
    service: Any,
) -> list[list[Any]]:
    """Fetch all rows from given tabs; returns combined rows with _tab column."""
    rows: list[list[Any]] = []
    for tab in tab_names:
        r = f"'{tab}'!A1:Z"
        try:
            resp = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=r,
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()
            vals = resp.get("values") or []
            for row in vals:
                rows.append(list(row) + [tab])
        except Exception:
            continue
    return rows


def get_sheets_service(service_account_path: str | None = None) -> Any:
    import os
    path = service_account_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not path and Path("E:/secrets/gcp/sa.json").exists():
        path = "E:/secrets/gcp/sa.json"
    if not path or not Path(path).exists():
        raise FileNotFoundError("Sheets service account JSON not found.")
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds)


def detect_transaction_columns(rows: list[list]) -> tuple[int, int, int, int]:
    """Return (date_col, company_col, source_col, amount_col, data_start_row)."""
    if not rows or len(rows[0]) < 2:
        return 0, 1, 2, 3, 0
    header = [str(c).strip().upper() for c in rows[0]]
    date_col = 0
    company_col = 1
    source_col = 2
    amount_col = 3
    for i, h in enumerate(header):
        if h in ("DATE", "Date"):
            date_col = i
        if h in ("COMPANY", "Company"):
            company_col = i
        if h in ("SOURCE", "DESCRIPTION", "DESC"):
            source_col = i
        if h in ("AMOUNT", "TOTAL", "Amount"):
            amount_col = i
    if "INITIALS" in header and "DATE" in header:
        date_col = header.index("DATE") if "DATE" in header else 1
        amount_col = 4 if len(header) > 4 else amount_col
    has_header = any(x in header for x in ("DATE", "AMOUNT", "SOURCE", "COMPANY", "TOTAL", "INITIALS"))
    start = 1 if has_header else 0
    return date_col, company_col, source_col, amount_col, start


def parse_amount(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    s = str(raw).strip().replace(",", "").replace("$", "").strip()
    if not s or s == "-":
        return None
    negative = "(" in s and ")" in s
    s = s.replace("(", "").replace(")", "").strip()
    try:
        val = float(s)
        return -val if negative else val
    except ValueError:
        return None


def fetch_payroll_sheet_labor_by_month(
    service: Any,
    config: dict[str, Any] | None = None,
    months_set: set[tuple[int, int]] | None = None,
) -> dict[tuple[int, int], float]:
    """
    Fetch Kylo PAYROLL tab(s) per year; aggregate payroll by (year, month).
    Layout: row 19 = employee names (one per column); col A from row 20 = dates, cols B,C,... = amounts per person.
    Returns {(y, m): total_dollars} (sum of all amounts per month).
    """
    from collections import defaultdict
    cfg = config or load_sources_config()
    payroll_cfg = (cfg or {}).get("payroll_sheet") or {}
    if not payroll_cfg:
        return {}
    by_ym: dict[tuple[int, int], float] = defaultdict(float)
    for year_key, sheet_cfg in payroll_cfg.items():
        if not isinstance(sheet_cfg, dict) or (isinstance(year_key, str) and year_key.startswith("_")):
            continue
        sid = sheet_cfg.get("spreadsheet_id")
        tab_name = sheet_cfg.get("tab") or "PAYROLL"
        header_row_1based = int(sheet_cfg.get("header_row", 19))
        date_col = int(sheet_cfg.get("date_column", 0))
        if not sid:
            continue
        r = f"'{tab_name}'!A1:Z"
        try:
            resp = service.spreadsheets().values().get(
                spreadsheetId=sid,
                range=r,
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()
        except Exception:
            continue
        vals = resp.get("values") or []
        if len(vals) < header_row_1based:
            continue
        header_row_idx = header_row_1based - 1
        header_row_raw = vals[header_row_idx] if header_row_idx < len(vals) else []
        data_start = header_row_1based
        for i in range(data_start, len(vals)):
            row = vals[i] if i < len(vals) else []
            if date_col >= len(row):
                continue
            ymd = parse_date_to_ymd(row[date_col])
            if not ymd:
                continue
            y, mo, _ = ymd
            for col in range(1, max(len(row), len(header_row_raw))):
                if col >= len(row):
                    continue
                amt = parse_amount(row[col])
                if amt is not None:
                    by_ym[(y, mo)] += abs(amt)
    result = {ym: round(tot, 2) for ym, tot in by_ym.items()}
    if months_set is not None:
        result = {ym: result[ym] for ym in result if ym in months_set}
    return result


def fetch_payroll_sheet_raw_rows(
    service: Any,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch all rows from PAYROLL tab(s) with parsed date, employee, and amount.
    Layout: row 19 = each person's name (one per column); col A from row 20 = date paid, cols B,C,... = amount paid to that person.
    Returns list of {"date_ymd", "date_str", "employee", "amount", "year_key"} (one per cell with an amount).
    """
    cfg = config or load_sources_config()
    payroll_cfg = (cfg or {}).get("payroll_sheet") or {}
    if not payroll_cfg:
        return []
    rows_out: list[dict[str, Any]] = []
    for year_key, sheet_cfg in payroll_cfg.items():
        if not isinstance(sheet_cfg, dict) or (isinstance(year_key, str) and year_key.startswith("_")):
            continue
        sid = sheet_cfg.get("spreadsheet_id")
        tab_name = sheet_cfg.get("tab") or "PAYROLL"
        header_row_1based = int(sheet_cfg.get("header_row", 19))
        date_col = int(sheet_cfg.get("date_column", 0))
        if not sid:
            continue
        r = f"'{tab_name}'!A1:Z"
        try:
            resp = service.spreadsheets().values().get(
                spreadsheetId=sid,
                range=r,
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()
        except Exception:
            continue
        vals = resp.get("values") or []
        if len(vals) < header_row_1based:
            continue
        header_row_idx = header_row_1based - 1
        header_row_raw = vals[header_row_idx] if header_row_idx < len(vals) else []
        data_start = header_row_1based
        for i in range(data_start, len(vals)):
            row = vals[i] if i < len(vals) else []
            if date_col >= len(row):
                continue
            ymd = parse_date_to_ymd(row[date_col])
            if not ymd:
                continue
            y, mo, d = ymd
            if not _date_acceptable_for_payroll(y, mo, d):
                continue
            date_str = f"{y:04d}-{mo:02d}-{d:02d}"
            for col in range(1, max(len(row), len(header_row_raw))):
                if col >= len(row):
                    continue
                amt = parse_amount(row[col])
                if amt is None or amt == 0:
                    continue
                employee = ""
                if col < len(header_row_raw) and header_row_raw[col] is not None:
                    employee = str(header_row_raw[col]).strip()
                if not employee:
                    employee = _column_letter(col)  # fallback: "B", "C", ...
                rows_out.append({
                    "date_ymd": (y, mo, d),
                    "date_str": date_str,
                    "employee": employee,
                    "amount": abs(amt),
                    "year_key": str(year_key),
                })
    return rows_out


def _column_letter(col_index: int) -> str:
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA, ..."""
    if col_index < 0:
        return "?"
    result = []
    n = col_index
    while True:
        result.append(chr(65 + (n % 26)))
        n = n // 26
        if n == 0:
            break
        n -= 1
    return "".join(reversed(result))


def _date_acceptable_for_payroll(y: int, mo: int, d: int, max_future_days: int = 31) -> bool:
    """True if (y, mo, d) is not too far in the future (avoids stray Excel serials or headers)."""
    from datetime import date
    try:
        dt = date(y, mo, d)
        today = date.today()
        return dt <= today + timedelta(days=max_future_days)
    except (ValueError, OverflowError):
        return False


def parse_date_to_ymd(raw: Any) -> tuple[int, int, int] | None:
    """Return (year, month, day) or None. Rejects Excel serials that yield far-future dates."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            base = datetime(1899, 12, 30)
            day_offset = int(float(raw))
            d = base + timedelta(days=day_offset)
            y, mo, day = d.year, d.month, d.day
            if not _date_acceptable_for_payroll(y, mo, day, max_future_days=60):
                return None
            return y, mo, day
        except (ValueError, OverflowError):
            return None
    s = str(raw).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3)) if m.lastindex >= 3 else 1
            if 1 <= mo <= 12 and 1900 <= y <= 2100:
                return y, mo, min(d, 28)
        except (ValueError, IndexError):
            pass
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        try:
            mo, d, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1900 <= y <= 2100:
                return y, mo, min(d, 28)
        except (ValueError, IndexError):
            pass
    return None
