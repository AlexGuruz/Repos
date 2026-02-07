from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.rules.jgdtruth_provider import fetch_rules_from_jgdtruth
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions


def _col_to_a1(col_index_0: int) -> str:
    s = ""
    n = col_index_0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose why approved rules are not posting")
    ap.add_argument("--company", required=True)
    args = ap.parse_args()

    cfg = load_config()
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == args.company.strip().upper()), None)
    if not comp:
        print(f"ERR unknown company: {args.company}")
        return 2

    spreadsheet_id = _extract_spreadsheet_id(str(comp.get("workbook_url")))
    intake_sid = _extract_spreadsheet_id(str(cfg.get("intake.workbook_url") or comp.get("workbook_url")))

    service = _get_service()
    # Build tab title resolver
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(title))").execute()
        titles = [s.get("properties", {}).get("title", "") for s in meta.get("sheets", [])]
    except Exception:
        titles = []
    title_map = {str(t).strip().lower(): str(t) for t in titles if isinstance(t, str)}

    # Static date map
    static_dates: List[str] = (
        cfg.get("intake.static_dates") or cfg.get("intake_static_dates.dates", []) or []
    )
    header_row = int(cfg.get("intake_static_dates.header_row", 19))
    first_row = int(cfg.get("intake_static_dates.first_row", 20))
    dates_to_row: Dict[str, int] = {d: (first_row + i) for i, d in enumerate(static_dates)}
    if not dates_to_row:
        print("ERR static dates list empty")
        return 3

    # Load transactions from TRANSACTIONS and BANK, tag tab
    txns: List[Dict[str, Any]] = []
    header_rows = int(cfg.get("intake.csv_processor.header_rows", 1))
    for tab in ("TRANSACTIONS", "BANK"):
        try:
            csv_content = download_petty_cash_csv(intake_sid, cfg.get("google.service_account_json_path"), sheet_name_override=tab)
            part = parse_csv_transactions(csv_content, header_rows=header_rows)
            for it in part:
                it["source_tab"] = tab
            txns.extend(part)
        except Exception:
            pass

    # Tally by (source, date)
    by_src_date: Dict[Tuple[str, str], float] = {}
    rows_by_src_date: Dict[Tuple[str, str], List[Tuple[str, int]]] = {}
    for t in txns:
        if (t.get("company_id") or "") != args.company:
            continue
        src = t.get("description") or ""
        dt_iso = t.get("posted_date") or ""
        if len(dt_iso) != 10:
            continue
        y, m, d = dt_iso.split("-")
        key_date = f"{int(m)}/{int(d)}/{int(y)%100:02d}"
        k = (src, key_date)
        by_src_date[k] = by_src_date.get(k, 0.0) + float(t.get("amount_cents", 0)) / 100.0
        try:
            rows_by_src_date.setdefault(k, []).append((t.get("source_tab") or "TRANSACTIONS", int(t.get("row_index_0based"))))
        except Exception:
            pass

    # Load rules
    rules = fetch_rules_from_jgdtruth(args.company)
    approved = [r for r in rules.values() if r.approved and r.target_sheet and r.target_header]
    if not approved:
        print("No approved rules found")
        return 0

    # Diagnose each rule
    print(f"Approved rules: {len(approved)}")
    for r in approved:
        src = r.source
        tab_key = str(r.target_sheet).strip().lower()
        resolved_tab = title_map.get(tab_key)
        tab_ok = bool(resolved_tab)
        header_ok = False
        col_a1 = None
        if tab_ok:
            rng = f"{resolved_tab}!{header_row}:{header_row}"
            try:
                res = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng, valueRenderOption="UNFORMATTED_VALUE").execute()
                headers = [str(c).strip() for c in (res.get("values", [[]])[0] if res.get("values") else [])]
                lowered = [h.lower() for h in headers]
                if r.target_header.strip().lower() in lowered:
                    header_ok = True
                    idx = lowered.index(r.target_header.strip().lower())
                    col_a1 = _col_to_a1(idx)
            except Exception:
                header_ok = False

        # Dates with non-zero totals for this source
        matches = []
        for dkey, row in dates_to_row.items():
            total = by_src_date.get((src, dkey))
            if total is None:
                continue
            if abs(total) < 1e-9:
                continue
            if tab_ok and header_ok:
                matches.append((dkey, f"{resolved_tab}!{col_a1}{row}", total))
            else:
                matches.append((dkey, None, total))

        status = "OK" if (tab_ok and header_ok) else ("NO_TAB" if not tab_ok else "NO_HEADER")
        sample = matches[:3]
        print(f"rule source='{src}' tab='{r.target_sheet}'->'{resolved_tab}' header='{r.target_header}' status={status} matches={len(matches)} sample={sample}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


