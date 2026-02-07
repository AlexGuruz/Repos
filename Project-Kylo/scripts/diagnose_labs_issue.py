#!/usr/bin/env python3
"""Diagnose LABS header issue for PUFFIN."""
import sys
import os
sys.path.insert(0, '.')

from services.rules.jgdtruth_provider import fetch_rules_from_jgdtruth
from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.common.retry import google_api_execute

# Set up environment
os.environ.setdefault("KYLO_SECRETS_DIR", os.path.join(os.getcwd(), ".secrets"))
os.environ.setdefault("KYLO_ACTIVE_YEARS", "2026")

cfg = load_config()
wb_url = cfg.get('year_workbooks.2026.output_workbook_url')
sid = _extract_spreadsheet_id(str(wb_url))

# Find rules with LABS header
rules = fetch_rules_from_jgdtruth('PUFFIN')
labs_rules = [r for r in rules.values() if r.target_header and 'LABS' in r.target_header.upper()]
print(f"\n=== Rules with LABS header: {len(labs_rules)} ===")
for r in labs_rules[:10]:
    print(f"  Source: '{r.source[:60]}'")
    print(f"    -> Target Sheet: '{r.target_sheet}'")
    print(f"    -> Header: '{r.target_header}'")
    print(f"    -> Approved: {r.approved}")
    print()

# Get PUFFIN tabs
service = _get_service()
meta = google_api_execute(
    service.spreadsheets().get(spreadsheetId=sid, fields='sheets(properties(title))'),
    label='get_tabs'
)
tabs = [s['properties']['title'] for s in meta.get('sheets', [])]
puffin_tabs = [t for t in tabs if 'PUFFIN' in t.upper()]

print(f"\n=== PUFFIN tabs found: {len(puffin_tabs)} ===")
for tab in puffin_tabs:
    print(f"  - {tab}")

# Check headers in PUFFIN tabs
header_row = int(cfg.get("intake_static_dates.header_row", 19))
print(f"\n=== Checking headers in row {header_row} ===")
for tab in puffin_tabs:
    try:
        qt = f"'{tab}'" if ' ' in tab else tab
        rng = f"{qt}!{chr(65)}:{chr(90)}{header_row}"  # A:Z row 19
        res = google_api_execute(
            service.spreadsheets().values().get(
                spreadsheetId=sid,
                range=rng,
                valueRenderOption="FORMATTED_VALUE",
            ),
            label=f'get_headers_{tab}',
        )
        headers = res.get('values', [[]])[0] if res.get('values') else []
        headers_clean = [h.strip() for h in headers if h and h.strip()]
        print(f"\n  Tab: {tab}")
        print(f"    Headers ({len(headers_clean)}): {', '.join(headers_clean[:20])}")
        labs_headers = [h for h in headers_clean if 'LABS' in h.upper()]
        if labs_headers:
            print(f"    ✓ Found LABS headers: {', '.join(labs_headers)}")
        else:
            print(f"    ✗ No LABS header found")
    except Exception as e:
        print(f"    Error reading {tab}: {e}")
