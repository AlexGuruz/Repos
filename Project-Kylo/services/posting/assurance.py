from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions


def _col_to_a1(col_index_0: int) -> str:
    s = ""
    n = col_index_0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def resolve_target_a1(
    service,
    spreadsheet_id: str,
    tab: str,
    header: str,
    date_key: str,
    *,
    header_row: int = 19,
    first_row: int = 20,
) -> Optional[str]:
    # Find column by header (row 19), case-insensitive/trimmed for resilience
    rng = f"{tab}!{header_row}:{header_row}"
    res = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=rng, valueRenderOption="UNFORMATTED_VALUE")
        .execute()
    )
    headers = [str(c).strip() for c in (res.get("values", [[]])[0] if res.get("values") else [])]
    try:
        idx = [h.lower() for h in headers].index((header or "").strip().lower())
    except ValueError:
        return None
    col_a1 = _col_to_a1(idx)

    # Row is from static dates map only – no API scan for dates
    cfg = load_config()
    static_dates: List[str] = (
        cfg.get("intake.static_dates") or cfg.get("intake_static_dates.dates", []) or []
    )
    if not static_dates:
        return None
    try:
        offset = static_dates.index(date_key)
    except ValueError:
        return None
    row_index = first_row + offset
    return f"{tab}!{col_a1}{row_index}"


def compute_expected_total(company: str, source: str, date_key: str) -> float:
    """Sum exact, case-sensitive matches for Description == source across TRANSACTIONS and BANK on date_key.

    date_key is M/D/YY; intake parser returns posted_date as YYYY-MM-DD, so convert.
    """
    # Convert M/D/YY -> YYYY-MM-DD (assumes 20YY)
    mm, dd, yy = date_key.split("/")
    y4 = f"20{int(yy):02d}"
    iso = f"{y4}-{int(mm):02d}-{int(dd):02d}"

    cfg = load_config()
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == company.strip().upper()), None)
    if not comp:
        return 0.0
    intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
    intake_sid = _extract_spreadsheet_id(str(intake_url))
    sa = cfg.get("google.service_account_json_path")
    header_rows = int(cfg.get("intake.csv_processor.header_rows", 1))

    total = 0.0
    for tab in ("TRANSACTIONS", "BANK"):
        try:
            csv_content = download_petty_cash_csv(intake_sid, sa, sheet_name_override=tab)
            txns = parse_csv_transactions(csv_content, header_rows=header_rows)
        except Exception:
            txns = []
        for t in txns:
            if (t.get("company_id") or "") != company:
                continue
            if (t.get("posted_date") or "") != iso:
                continue
            # Exact, case-sensitive, no trim
            if (t.get("description") or "") != source:
                continue
            total += float(t.get("amount_cents", 0)) / 100.0
    return total


def write_with_verification(
    service,
    spreadsheet_id: str,
    a1: str,
    value: float,
    *,
    retries: int = 3,
    epsilon: float = 0.005,
    value_input_option: str = "RAW",
) -> bool:
    for attempt in range(retries):
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=a1,
            valueInputOption=value_input_option,
            body={"values": [[value]]},
        ).execute()
        # Read back
        res = (
            service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=a1,
                valueRenderOption="UNFORMATTED_VALUE",
            ).execute()
        )
        got = None
        try:
            raw = res.get("values", [[None]])[0][0]
            got = float(raw)
        except Exception:
            got = None
        if got is not None and abs(got - float(value)) <= epsilon:
            return True
        time.sleep(0.5 * (attempt + 1))
    return False


__all__ = [
    "resolve_target_a1",
    "compute_expected_total",
    "write_with_verification",
]


