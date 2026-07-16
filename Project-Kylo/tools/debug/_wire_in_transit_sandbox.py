"""
Wire transfer day-nets + In Transit (K) on sandbox BALANCE / INCOME helpers.

SANDBOX ONLY: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw

1) Pull TX+BANK intake → transfer legs → match (±3 days)
2) Write INCOME helpers: Transfer Cash Net (Z), Transfer Bank Net (AA)
3) Rewrite BALANCE I/J to include transfer nets; K = running In Transit
4) Print match stats + day1/mid Available
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

os.environ["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.posting.transfer_matcher import (
    legs_from_intake_rows,
    match_transfers,
    running_in_transit,
)
from services.sheets.poster import _extract_spreadsheet_id

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
OPENING_BANK = 4845.52
OPENING_CASH = 6673.09
WINDOW_DAYS = 3

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries: int = 12):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status in (429, 503):
                wait = 35 + i * 12
                print(f"  rate-limit sleep {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("retries exhausted")


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def get(rng: str, render: str = "UNFORMATTED_VALUE"):
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def update(rng: str, values, raw: bool = False):
    retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW" if raw else "USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


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


def col_letter(n1: int) -> str:
    s = ""
    n = n1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


print("=== Load intake transfers ===")
cfg = load_config()
sa_path = cfg.get("google.service_account_json_path")
intake_sid = _extract_spreadsheet_id(
    (cfg.get("year_workbooks") or {}).get("2026", {}).get("intake_workbook_url")
)
rows = []
for tab in ("TRANSACTIONS", "BANK"):
    csv = download_petty_cash_csv(intake_sid, sa_path, sheet_name_override=tab)
    proc = PettyCashCSVProcessor(
        csv,
        header_rows=int(cfg.get("intake.csv_processor.header_rows", 19)),
        source_tab=tab,
        source_spreadsheet_id=intake_sid,
    )
    for t in proc.parse_transactions():
        t["source_tab"] = tab
        rows.append(t)
    print(f"  {tab}: {len(rows)} cumulative rows")

legs = legs_from_intake_rows(rows)
print(f"  transfer legs: {len(legs)}")
result = match_transfers(legs, window_days=WINDOW_DAYS, amount_tolerance=0.02)
print(f"  matches: {len(result.matches)} unmatched: {len(result.unmatched)}")
by_fam: Dict[str, int] = {}
for m in result.matches:
    by_fam[m.family] = by_fam.get(m.family, 0) + 1
print(f"  by family: {by_fam}")
un_side: Dict[str, int] = {}
for u in result.unmatched:
    un_side[u.side] = un_side.get(u.side, 0) + 1
print(f"  unmatched sides: {un_side}")

# Date spine from BALANCE
dates_raw = get(a1("BALANCE", "B20:B400"))
spine: List[date] = []
for r in dates_raw:
    d = parse_date(r[0] if r else None)
    spine.append(d)  # may be None for blank

valid_dates = [d for d in spine if d]
k_run = running_in_transit(result.by_date, valid_dates)

# Ensure INCOME headers for transfer helpers at AB / AC (cols 28/29).
# Do NOT overwrite Z/AA — those hold CASH / CITIZENS IN/OUT on this layout.
inc_h = [str(c).strip() if c is not None else "" for c in (get(a1("INCOME", "A19:AZ19")) or [[]])[0]]
while len(inc_h) < 29:
    inc_h.append("")
inc_h[27] = "Transfer Cash Net"
inc_h[28] = "Transfer Bank Net"
update(a1("INCOME", "A19"), [inc_h], raw=True)
print("  INCOME AB/AC transfer helper headers set")

xfer_cash_col: List[List[Any]] = []
xfer_bank_col: List[List[Any]] = []
for d in spine:
    if d and d in result.by_date:
        c = round(result.by_date[d].cash, 2)
        b = round(result.by_date[d].bank, 2)
        xfer_cash_col.append([c if abs(c) >= 0.005 else ""])
        xfer_bank_col.append([b if abs(b) >= 0.005 else ""])
    else:
        xfer_cash_col.append([""])
        xfer_bank_col.append([""])

update(a1("INCOME", "AB20"), xfer_cash_col, raw=True)
time.sleep(1.2)
update(a1("INCOME", "AC20"), xfer_bank_col, raw=True)
print("  INCOME transfer day-nets written")

# BALANCE I/J/K/L
print("=== Rewrite BALANCE with transfers + In Transit ===")
rows_i, rows_j, rows_k, rows_l = [], [], [], []
k_vals: List[List[Any]] = []
for i, d in enumerate(spine):
    r = 20 + i
    bank_day = (
        f"(IFERROR(INCOME!Y{r},0)+IFERROR(INCOME!AC{r},0)"
        f"+IFERROR('BANK EXPENSES'!B{r},0)+IFERROR(PAYROLL!W{r},0)"
        f"+IFERROR(JGD!L{r},0)+IFERROR('CC Payments'!B{r},0))"
    )
    cash_day = (
        f"(IFERROR(INCOME!X{r},0)+IFERROR(INCOME!AB{r},0)"
        f"+IFERROR('CASH EXPENSES'!B{r},0)+IFERROR(PAYROLL!V{r},0)"
        f"+IFERROR(JGD!K{r},0)+IFERROR('NUGZ COG'!B{r},0)"
        f"+IFERROR('NON CANNABIS'!B{r},0)+IFERROR(ALLOCATED!B{r},0))"
    )
    if i == 0:
        rows_i.append([f"={OPENING_BANK}+{bank_day}"])
        rows_j.append([f"={OPENING_CASH}+{cash_day}"])
    else:
        rows_i.append([f"=I{r-1}+{bank_day}"])
        rows_j.append([f"=J{r-1}+{cash_day}"])
    if d and d in k_run:
        k_vals.append([k_run[d]])
    else:
        k_vals.append([0])
    rows_l.append([f"=I{r}+J{r}+K{r}"])

update(a1("BALANCE", "I20"), rows_i, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "J20"), rows_j, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "K20"), k_vals, raw=True)
time.sleep(1)
update(a1("BALANCE", "L20"), rows_l, raw=False)

update(
    a1("BALANCE", "A18:L18"),
    [[
        "",
        "",
        "Payroll helpers",
        "Expenses twins",
        "COG (NUGZ only)",
        "ATM/JGD (+K bridge)",
        "CC bank",
        "Income + transfers",
        "BANK EOD",
        "CASH EOD",
        "IN TRANSIT",
        "AVAILABLE = I+J+K",
    ]],
    raw=True,
)

# Snapshot
time.sleep(2)
day1 = get(a1("BALANCE", "I20:L20"))
print("day1 IJKL", day1)
mid_row = None
for i, d in enumerate(spine):
    if d == date(2026, 7, 16):
        mid_row = 20 + i
        break
if mid_row:
    mid = get(a1("BALANCE", f"I{mid_row}:L{mid_row}"))
    print(f"mid 7/16 IJKL", mid)
    if mid and mid[0]:
        I, J, K, L = [float(x or 0) for x in (mid[0] + [0, 0, 0, 0])[:4]]
        print(f"  I={I:,.2f} J={J:,.2f} K={K:,.2f} L={L:,.2f}")

print("DONE transfer / In Transit wire")
