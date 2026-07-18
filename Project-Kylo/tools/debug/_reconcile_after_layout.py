"""Force INCOME!A19=DATE and reconcile Cash/Bank EOD vs ledgers (sandbox)."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
OPENING_BANK = 4845.52

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn):
    for i in range(12):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) and e.resp.status in (429, 503):
                time.sleep(20 + i * 12)
                continue
            raise


def get(rng, render="UNFORMATTED_VALUE"):
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def update(rng, values):
    retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW",
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
            pass
    return None


def to_float(v) -> float:
    if v in (None, ""):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("$", "").replace(",", "").replace("(", "-").replace(")", "").strip()
    if s in ("", "-"):
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


# Force DATE header
update("'INCOME'!A19", [["DATE"]])
print("INCOME A19:B19 =", get("'INCOME'!A19:B19", "FORMATTED_VALUE"))

# Reconcile using FULL columns (same as BALANCE SUMIFS)
tx = get("'TRANSACTIONS'!A:D")
bk = get("'BANK'!A:D")
cash_by: dict[date, float] = {}
bank_by: dict[date, float] = {}
for r in tx[1:]:  # skip header-ish
    d = parse_date(r[0] if r else None)
    if not d:
        continue
    amt = to_float(r[3] if len(r) > 3 else 0)
    cash_by[d] = round(cash_by.get(d, 0.0) + amt, 2)
for r in bk[1:]:
    d = parse_date(r[0] if r else None)
    if not d:
        continue
    amt = to_float(r[3] if len(r) > 3 else 0)
    bank_by[d] = round(bank_by.get(d, 0.0) + amt, 2)

bal = get("'BALANCE'!B20:L400")
max_diff_j = 0.0
max_diff_i = 0.0
checks = []
c_run = 0.0
b_run = OPENING_BANK
# Build cumulative for all dates through D0
all_dates = sorted(set(cash_by) | set(bank_by))
cum_c: dict[date, float] = {}
cum_b: dict[date, float] = {}
for d in all_dates:
    c_run = round(c_run + cash_by.get(d, 0.0), 2)
    b_run = round(b_run + bank_by.get(d, 0.0), 2)
    cum_c[d] = c_run
    cum_b[d] = b_run

for i, r in enumerate(bal):
    d = parse_date(r[0] if r else None)
    if not d or d > date(2026, 7, 17):
        continue
    cells = (r + [""] * 12)[:12]
    i_b = to_float(cells[7])
    j_c = to_float(cells[8])
    lc = cum_c.get(d)
    lb = cum_b.get(d)
    # BALANCE SUMIFS includes all rows with date<=d; our cum is exact if we have all dates
    # For dates with no tx, carry forward last
    if lc is None:
        prior = [x for x in all_dates if x <= d]
        lc = cum_c[prior[-1]] if prior else 0.0
    if lb is None:
        prior = [x for x in all_dates if x <= d]
        lb = cum_b[prior[-1]] if prior else OPENING_BANK
    dj = abs(round(j_c - lc, 2))
    di = abs(round(i_b - lb, 2))
    max_diff_j = max(max_diff_j, dj)
    max_diff_i = max(max_diff_i, di)
    if d in (date(2026, 1, 1), date(2026, 7, 15), date(2026, 7, 16), date(2026, 7, 17)):
        checks.append((d, i_b, lb, di, j_c, lc, dj))

print("sample actuals (date, I, ledgerB, dI, J, ledgerC, dJ):")
for c in checks:
    print(" ", c)
print(f"max |I-ledger| through D0 = {max_diff_i:.4f}")
print(f"max |J-ledger| through D0 = {max_diff_j:.4f}")

# Projected spot
print("\nProjected spot G/H:")
for d in (date(2026, 7, 19), date(2026, 7, 20), date(2026, 7, 22)):
    for i, r in enumerate(bal):
        if parse_date(r[0] if r else None) == d:
            cells = (r + [""] * 12)[:12]
            print(d, "G/H/I/J/K/L", cells[5:11])
            break
