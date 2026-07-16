"""
Reconcile BALANCE Cash EOD (J) against the TRANSACTIONS tab running balance.

Owner model: TRANSACTIONS is the physical cash pool ledger. Every AMOUNT is a
cash movement (income into pool +, expense/ATM/TO BANK -, FROM BANK +).
So the cumulative sum of TRANSACTIONS!AMOUNT per day == cash on hand that day.

This prints, per day:
  - cash_ledger  = cumulative TRANSACTIONS AMOUNT (true cash on hand)
  - balance_J    = BALANCE!J (reconstructed Cash EOD)
  - diff         = balance_J - cash_ledger
and summarizes the largest recurring divergence sources by SOURCE label.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

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
    if v is None or v == "":
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
    neg = False
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
        neg = True
    try:
        val = float(s)
        return -val if neg else val
    except Exception:
        return 0.0


# --- 1) TRANSACTIONS ledger (raw AMOUNT col D, unfiltered) ---
rows = (
    svc.spreadsheets()
    .values()
    .get(
        spreadsheetId=INTAKE_SID,
        range="'TRANSACTIONS'!A2:F5000",
        valueRenderOption="UNFORMATTED_VALUE",
    )
    .execute()
    .get("values", [])
)

day_cash: Dict[date, float] = defaultdict(float)
day_by_type: Dict[date, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
src_total: Dict[str, float] = defaultdict(float)
src_count: Dict[str, int] = defaultdict(int)
opening_row = 0.0
for r in rows:
    if not r:
        continue
    r = list(r) + [""] * 6
    d = parse_date(r[0])
    amt = fnum(r[3])
    src = " ".join(str(r[2]).upper().split())
    typ = str(r[4]).strip().upper()
    if d is None:
        continue
    if src == "START OF YEAR":
        opening_row += amt
        continue  # opening handled separately
    day_cash[d] += amt
    day_by_type[d][typ] += amt
    src_total[src] += amt
    src_count[src] += 1

print(f"TRANSACTIONS opening (START OF YEAR rows): {opening_row:,.2f}")
OPENING_CASH = 6673.09

# --- 2) BALANCE J per day ---
bvals = (
    svc.spreadsheets()
    .values()
    .batchGet(
        spreadsheetId=OUTPUT_SID,
        ranges=["'BALANCE'!B20:B400", "'BALANCE'!J20:J400"],
        valueRenderOption="UNFORMATTED_VALUE",
    )
    .execute()
    .get("valueRanges", [])
)
bdates = bvals[0].get("values", [])
jcol = bvals[1].get("values", [])
balance_J: Dict[date, float] = {}
for i, r in enumerate(bdates):
    d = parse_date(r[0] if r else None)
    if d:
        balance_J[d] = fnum(jcol[i][0]) if i < len(jcol) and jcol[i] else 0.0

# --- 3) Build cumulative cash ledger ---
all_days = sorted(day_cash.keys())
run = OPENING_CASH
cash_ledger: Dict[date, float] = {}
for d in all_days:
    run += day_cash[d]
    cash_ledger[d] = round(run, 2)

# --- 4) Compare on key dates ---
targets = [
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 2, 1),
    date(2026, 3, 1),
    date(2026, 4, 1),
    date(2026, 5, 1),
    date(2026, 6, 1),
    date(2026, 6, 27),
    date(2026, 7, 15),
    date(2026, 7, 16),
]
print("\n date        cash_ledger   balance_J        diff")
for t in targets:
    cl = cash_ledger.get(t)
    bj = balance_J.get(t)
    if cl is None or bj is None:
        print(f" {t}   ledger={cl} balance_J={bj}")
        continue
    print(f" {t}  {cl:12,.2f} {bj:12,.2f} {bj-cl:12,.2f}")

# --- 5) Divergence scan ---
diffs = []
for d in all_days:
    if d > date(2026, 7, 16):
        continue
    if d in balance_J:
        diffs.append((d, balance_J[d] - cash_ledger[d]))
if diffs:
    last_d, last_diff = diffs[-1], diffs[-1]
    import statistics

    vals = [x[1] for x in diffs]
    print(f"\nDiff stats (balance_J - cash_ledger) over {len(diffs)} days:")
    print(f"  min={min(vals):,.2f}  max={max(vals):,.2f}  mean={statistics.mean(vals):,.2f}")
    print(f"  last day {diffs[-1][0]} diff={diffs[-1][1]:,.2f}")
    print(f"  cash ledger min: {min((cash_ledger[d], d) for d in all_days if d<=date(2026,7,16))}")

# --- 6) Which SOURCE labels are the biggest cash movers (context) ---
print("\nTop cash sources by |cumulative amount|:")
top = sorted(src_total.items(), key=lambda kv: -abs(kv[1]))[:25]
for src, tot in top:
    print(f"  {src[:32]:32s} {tot:14,.2f}  (n={src_count[src]})")

# --- 7) Type totals through mid-year ---
print("\nType totals thru 7/16:")
type_tot: Dict[str, float] = defaultdict(float)
for d in all_days:
    if d > date(2026, 7, 16):
        continue
    for typ, v in day_by_type[d].items():
        type_tot[typ] += v
for typ, v in sorted(type_tot.items(), key=lambda kv: -abs(kv[1])):
    print(f"  {typ or '(blank)':12s} {v:14,.2f}")
