"""
Rebuild BALANCE so Cash EOD / Bank EOD are the ACTUAL account ledgers.

Owner truth model:
  Cash EOD (J) = running balance of TRANSACTIONS tab (the physical cash pool ledger)
  Bank EOD (I) = opening bank + running balance of BANK tab (bank statement)
  In Transit (K) = running float of TRUE transfers still mid-flight
                   (TO BANK<->DEPOSIT, FROM BANK<->WITHDRAW timing gaps only)
  AVAILABLE (L) = I + J + K

ATM LOAD (cash into machine) and SWITCH (ATM revenue to bank) are NOT a $-for-$
transfer pair, so they are NOT netted through In Transit — they stay as real
cash-out / bank-in on their respective ledgers.

J/I are live SUMIFS against the TRANSACTIONS / BANK tabs (same sandbox workbook),
so they always match those tabs' running balances by date.

SANDBOX ONLY: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
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
WINDOW_DAYS = 3

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries=12):
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


def a1(tab, rng):
    return "'" + tab.replace("'", "''") + "'!" + rng


def get(rng, render="UNFORMATTED_VALUE"):
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def update(rng, values, raw=False):
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


# --- date spine from BALANCE ---
dates_raw = get(a1("BALANCE", "B20:B400"))
spine: List[Optional[date]] = [parse_date(r[0] if r else None) for r in dates_raw]
n = len(spine)
print(f"BALANCE days={n}")

# --- transfer legs (TRUE transfers only: drop atm) for In Transit ---
cfg = load_config()
sa_path = cfg.get("google.service_account_json_path")
intake_sid = _extract_spreadsheet_id(
    (cfg.get("year_workbooks") or {}).get("2026", {}).get("intake_workbook_url")
)
rows: List[dict] = []
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

legs = [l for l in legs_from_intake_rows(rows) if l.family in ("to_bank", "from_bank")]
result = match_transfers(legs, window_days=WINDOW_DAYS, amount_tolerance=0.02)
valid_dates = [d for d in spine if d]
k_run = running_in_transit(result.by_date, valid_dates)
print(
    f"transfer legs (to/from bank only)={len(legs)} "
    f"matched={len(result.matches)} unmatched={len(result.unmatched)}"
)

# --- Build formulas ---
# J = cash ledger: cumulative TRANSACTIONS!D where TRANSACTIONS!A <= this date.
#     START OF YEAR (6673.09) lives in TRANSACTIONS so it seeds the opening.
# I = OPENING_BANK + cumulative BANK!D where BANK!A <= this date.
rows_i: List[List[Any]] = []
rows_j: List[List[Any]] = []
rows_k: List[List[Any]] = []
rows_l: List[List[Any]] = []
for i, d in enumerate(spine):
    r = 20 + i
    # SUMIFS by date serial in B{r}
    rows_j.append(
        [f'=IFERROR(SUMIFS(TRANSACTIONS!$D:$D,TRANSACTIONS!$A:$A,"<="&$B{r}),0)']
    )
    rows_i.append(
        [f'={OPENING_BANK}+IFERROR(SUMIFS(BANK!$D:$D,BANK!$A:$A,"<="&$B{r}),0)']
    )
    rows_k.append([round(k_run.get(d, 0.0), 2) if d else 0])
    rows_l.append([f"=I{r}+J{r}+K{r}"])

print("writing I/J/K/L ...")
update(a1("BALANCE", "J20"), rows_j, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "I20"), rows_i, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "K20"), rows_k, raw=True)
time.sleep(1.2)
update(a1("BALANCE", "L20"), rows_l, raw=False)
time.sleep(1.2)

# --- Category breakdown cols C-H: keep as informational day nets from ledgers ---
# C = cash day net (TRANSACTIONS), D = bank day net (BANK), leave E-H blank/legacy.
rows_c: List[List[Any]] = []
rows_d: List[List[Any]] = []
for i, d in enumerate(spine):
    r = 20 + i
    if i == 0:
        rows_c.append(["=J20-6673.09"])
        rows_d.append([f"=I20-{OPENING_BANK}"])
    else:
        rows_c.append([f"=J{r}-J{r-1}"])
        rows_d.append([f"=I{r}-I{r-1}"])
update(a1("BALANCE", "C20"), rows_c, raw=False)
time.sleep(1.2)
update(a1("BALANCE", "D20"), rows_d, raw=False)

update(
    a1("BALANCE", "A18:L19"),
    [
        [
            "",
            "",
            "Cash day net (TRANSACTIONS)",
            "Bank day net (BANK)",
            "",
            "",
            "",
            "",
            "BANK EOD = BANK ledger",
            "CASH EOD = TRANSACTIONS ledger",
            "IN TRANSIT (TO/FROM BANK float)",
            "AVAILABLE = I+J+K",
        ],
        [
            "",
            "DATE",
            "Cash dNet",
            "Bank dNet",
            "",
            "",
            "",
            "",
            "Bank EOD",
            "Cash EOD",
            "In Transit",
            "AVAILABLE",
        ],
    ],
    raw=True,
)

# --- Verify readback against python ledger on a few dates ---
time.sleep(2)
check = get(a1("BALANCE", "B20:L400"))
print("\n date          I(bank)      J(cash)        K        L(avail)")
want = {
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 6, 27),
    date(2026, 7, 15),
    date(2026, 7, 16),
}
for r in check:
    d = parse_date(r[0] if r else None)
    if d in want:
        row = list(r) + [""] * 11
        def f(x):
            try:
                return float(x or 0)
            except Exception:
                return 0.0
        I, J, K, L = f(row[7]), f(row[8]), f(row[9]), f(row[10])
        print(f" {d}  {I:11,.2f} {J:11,.2f} {K:9,.2f} {L:11,.2f}")

print("\nDONE rebuild BALANCE from ledgers")
