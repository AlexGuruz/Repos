"""Reconcile BALANCE Bank EOD (I) vs BANK tab running balance."""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, Optional

sys.path.insert(0, r"E:\Repos\Project-Kylo")
os.environ["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"

from google.oauth2 import service_account
from googleapiclient.discovery import build

from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id

SA = r"E:/secrets/gcp/sa.json"
OUTPUT_SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
cfg = load_config()
INTAKE_SID = _extract_spreadsheet_id(
    (cfg.get("year_workbooks") or {}).get("2026", {}).get("intake_workbook_url")
)
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def parse_date(v) -> Optional[date]:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def fnum(v) -> float:
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("$", "").replace(",", "")
    if s in ("", "-"):
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return 0.0


# BANK tab: DATE(A), COMPANY(B), SOURCE(C), AMOUNT(D)
rows = (
    svc.spreadsheets()
    .values()
    .get(spreadsheetId=INTAKE_SID, range="'BANK'!A2:F5000", valueRenderOption="UNFORMATTED_VALUE")
    .execute()
    .get("values", [])
)
day_bank: Dict[date, float] = defaultdict(float)
src_total: Dict[str, float] = defaultdict(float)
opening_rows = 0.0
for r in rows:
    if not r:
        continue
    r = list(r) + [""] * 6
    d = parse_date(r[0])
    amt = fnum(r[3])
    src = " ".join(str(r[2]).upper().split())
    if d is None:
        continue
    if src == "START OF YEAR":
        opening_rows += amt
        continue
    day_bank[d] += amt
    src_total[src] += amt

print(f"BANK START OF YEAR rows sum: {opening_rows:,.2f}")

OPENING_BANK = 4845.52
all_days = sorted(day_bank.keys())
run = OPENING_BANK + opening_rows if opening_rows else OPENING_BANK
# If BANK has its own opening rows, don't double add literal
if opening_rows:
    run = opening_rows
bank_ledger: Dict[date, float] = {}
r2 = OPENING_BANK
for d in all_days:
    r2 += day_bank[d]
    bank_ledger[d] = round(r2, 2)

bvals = (
    svc.spreadsheets()
    .values()
    .batchGet(
        spreadsheetId=OUTPUT_SID,
        ranges=["'BALANCE'!B20:B400", "'BALANCE'!I20:I400"],
        valueRenderOption="UNFORMATTED_VALUE",
    )
    .execute()
    .get("valueRanges", [])
)
bdates = bvals[0].get("values", [])
icol = bvals[1].get("values", [])
balance_I: Dict[date, float] = {}
for i, r in enumerate(bdates):
    d = parse_date(r[0] if r else None)
    if d:
        balance_I[d] = fnum(icol[i][0]) if i < len(icol) and icol[i] else 0.0

print("\n date        bank_ledger    balance_I        diff")
for t in [
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 4, 1),
    date(2026, 6, 1),
    date(2026, 7, 15),
]:
    bl = bank_ledger.get(t)
    bi = balance_I.get(t)
    if bl is None or bi is None:
        print(f" {t}  ledger={bl} I={bi}")
        continue
    print(f" {t}  {bl:12,.2f} {bi:12,.2f} {bi-bl:12,.2f}")

diffs = [balance_I[d] - bank_ledger[d] for d in all_days if d <= date(2026, 7, 15) and d in balance_I]
if diffs:
    print(f"\nDiff(I - bank_ledger): min={min(diffs):,.2f} max={max(diffs):,.2f} last={diffs[-1]:,.2f}")

print("\nTop BANK sources:")
for src, tot in sorted(src_total.items(), key=lambda kv: -abs(kv[1]))[:20]:
    print(f"  {src[:32]:32s} {tot:14,.2f}")
