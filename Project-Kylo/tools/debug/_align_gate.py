"""Final gate: critical sandbox checks must all pass."""
from __future__ import annotations

import sys
import time
from datetime import date, datetime, timedelta
from typing import Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

FAILS = []
OKS = []


def ok(m):
    OKS.append(m)
    print("OK ", m)


def fail(m):
    FAILS.append(m)
    print("FAIL", m)


def get(rng, render="UNFORMATTED_VALUE"):
    return (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def parse_date(v) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


# 1 tabs
meta = svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute()
vis = []
hid = []
for s in meta.get("sheets", []):
    p = s["properties"]
    (hid if p.get("hidden") else vis).append(p["title"])
must_hide = [
    "CASH PAYROLL",
    "BANK PAYROLL",
    "CASH JGD",
    "BANK JGD",
    "BANK NUGZ COG",
    "CASH INCOME",
    "BANK INCOME",
    "JGD EXPENSES (LEGACY)",
]
for t in must_hide:
    if t not in vis:
        ok(f"not visible: {t}")
    else:
        fail(f"still visible: {t}")

# 2 headers (batch sheet headers once to avoid Sheets 429)
needed_sheets = set()
rules_rows = {}
for rules in ("TRANSACTIONS RULES", "BANK RULES"):
    rows = get(f"'{rules}'!A1:C300")
    rules_rows[rules] = rows
    for r in rows[1:]:
        if len(r) >= 2 and str(r[1]).strip():
            needed_sheets.add(str(r[1]).strip())

header_cache = {}
ranges = [f"'{s}'!A19:BZ19" for s in sorted(needed_sheets)]
# batchGet in chunks
for i in range(0, len(ranges), 20):
    chunk = ranges[i : i + 20]
    time.sleep(1.5 if i else 0)
    resp = (
        svc.spreadsheets()
        .values()
        .batchGet(spreadsheetId=SID, ranges=chunk, valueRenderOption="UNFORMATTED_VALUE")
        .execute()
    )
    for vr in resp.get("valueRanges", []):
        rng = vr.get("range", "")
        # "'SHEET'!A19:BZ19" or SHEET!A19:BZ19
        title = rng.split("!")[0].strip("'")
        vals = vr.get("values", [])
        header_cache[title] = {
            str(c).strip().upper() for c in (vals[0] if vals else []) if str(c).strip()
        }

for rules, rows in rules_rows.items():
    miss = 0
    for r in rows[1:]:
        if len(r) < 3:
            continue
        sheet, header = str(r[1]).strip(), str(r[2]).strip()
        exist = header_cache.get(sheet, set())
        if header.upper() not in exist:
            miss += 1
            fail(f"missing {sheet}/{header}")
    if miss == 0:
        ok(f"{rules}: all headers present")

# 3 BALANCE
b1 = get("'BALANCE'!I20:L20")[0]
I, J, K, L = [float(x or 0) for x in (b1 + [0, 0, 0, 0])[:4]]
if abs(I - 4845.52) < 0.05:
    ok(f"day1 bank {I}")
else:
    fail(f"day1 bank {I}")
# Day1 Available = opening bank + day1 cash ledger (no ATM in K anymore).
if abs(L - 12036.96) < 1.0:
    ok(f"day1 available {L}")
else:
    fail(f"day1 available {L}")
if abs(I + J + K - L) < 0.05:
    ok("day1 L=I+J+K")
else:
    fail("day1 L!=I+J+K")

# mid-year available should be sane (<100k abs and not deep negative)
# find 7/16
dates = get("'BALANCE'!B20:B400")
row216 = None
for i, r in enumerate(dates):
    d = parse_date(r[0] if r else None)
    if d == date(2026, 7, 16):
        row216 = 20 + i
        break
if row216:
    mid = get(f"'BALANCE'!I{row216}:L{row216}")[0]
    Im, Jm, Km, Lm = [float(x or 0) for x in (mid + [0, 0, 0, 0])[:4]]
    print(f"mid 7/16 I={Im:,.2f} J={Jm:,.2f} L={Lm:,.2f}")
    if abs(Im + Jm + Km - Lm) < 0.1:
        ok("mid L=I+J+K")
    else:
        fail("mid L!=I+J+K")
    if Lm > -50000 and Lm < 200000:
        ok(f"mid available sane {Lm:,.2f}")
    else:
        fail(f"mid available insane {Lm:,.2f}")

# 4 payroll helpers are values not all-cash formulas dumping bank ACH into cash only incorrectly
# Bank net should be nonzero if bank payroll exists
pw = get("'PAYROLL'!W20:W400")
pv = get("'PAYROLL'!V20:V400")
bank_sum = 0.0
cash_sum = 0.0
for r in pw:
    try:
        bank_sum += float(r[0])
    except Exception:
        pass
for r in pv:
    try:
        cash_sum += float(r[0])
    except Exception:
        pass
print(f"payroll helpers cash={cash_sum:,.2f} bank={bank_sum:,.2f}")
if abs(cash_sum) + abs(bank_sum) > 1000:
    ok("payroll helpers populated")
else:
    fail("payroll helpers empty")
# bank helper should not stay stuck at 0 if greg bank exists
if abs(bank_sum) > 100:
    ok(f"payroll bank net nonzero {bank_sum:,.2f}")
else:
    fail(f"payroll bank net still ~0 ({bank_sum})")

# 5 projections on BANK EXPENSES future
TODAY = date(2026, 7, 15)
be = get("'BANK EXPENSES'!A19:AZ400")
hdr = [str(c).strip() for c in be[0]]
fut = 0
for r in be[1:]:
    d = parse_date(r[0] if r else None)
    if d is None or d <= TODAY:
        continue
    for i, c in enumerate(r):
        if i < 2:
            continue
        try:
            if float(c) != 0:
                fut += 1
        except Exception:
            pass
if fut >= 50:
    ok(f"BANK EXPENSES future projections {fut}")
else:
    fail(f"BANK EXPENSES future projections {fut}")

# 6 Cash EOD (J) reads the TRANSACTIONS ledger directly
form_j = str(get("'BALANCE'!J20", "FORMULA"))
if "TRANSACTIONS" in form_j and "SUMIFS" in form_j.upper():
    ok("Cash EOD = TRANSACTIONS running ledger")
else:
    fail(f"Cash EOD not sourced from TRANSACTIONS ledger: {form_j[:60]}")

# 6b Cash EOD matches TRANSACTIONS cumulative to the penny (sample dates)
def _cash_ledger_check():
    intake = get("'TRANSACTIONS'!A2:F5000")
    day_net = {}
    for row in intake:
        if not row:
            continue
        row = list(row) + [""] * 6
        d = parse_date(row[0])
        src = " ".join(str(row[2]).upper().split())
        if d is None:
            continue
        try:
            amt = float(str(row[3]).replace("$", "").replace(",", "")) if not isinstance(row[3], (int, float)) else float(row[3])
        except Exception:
            amt = 0.0
        day_net[d] = day_net.get(d, 0.0) + amt
    jrows = get("'BALANCE'!B20:B400")
    jvals = get("'BALANCE'!J20:J400")
    run = 0.0
    worst = 0.0
    for i, r in enumerate(sorted({d for d in day_net})):
        pass
    # cumulative along BALANCE spine
    cum = 0.0
    ordered = sorted(day_net)
    running = {}
    c = 0.0
    for d in ordered:
        c += day_net[d]
        running[d] = round(c, 2)
    for i, r in enumerate(jrows):
        d = parse_date(r[0] if r else None)
        if not d or d > date(2026, 7, 15):
            continue
        jv = float(jvals[i][0]) if i < len(jvals) and jvals[i] else 0.0
        led = running.get(d)
        if led is not None:
            worst = max(worst, abs(jv - led))
    return worst

worst = _cash_ledger_check()
if worst < 0.05:
    ok(f"Cash EOD ties to ledger (max diff {worst:.4f})")
else:
    fail(f"Cash EOD diverges from ledger (max diff {worst:,.2f})")

# 7 Bank EOD (I) reads the BANK ledger directly
form_i = str(get("'BALANCE'!I20", "FORMULA"))
if "BANK" in form_i and "SUMIFS" in form_i.upper():
    ok("Bank EOD = BANK running ledger")
else:
    fail(f"Bank EOD not sourced from BANK ledger: {form_i[:60]}")

k_vals = get("'BALANCE'!K20:K400")
k_nonzero = 0
k_last = 0.0
for r in k_vals:
    try:
        kv = float(r[0])
        if abs(kv) >= 0.5:
            k_nonzero += 1
        k_last = kv
    except Exception:
        pass
# After transfers, mid-year K should usually be nonzero some days OR last K can be small
if k_nonzero >= 1 or abs(k_last) >= 0.5:
    ok(f"In Transit populated (nonzero days={k_nonzero}, last={k_last:,.2f})")
else:
    # Still OK if everything matched same-day — but warn as fail for this sandbox
    fail(f"In Transit still all zeros (last={k_last})")

print(f"\nGATE fails={len(FAILS)} oks={len(OKS)}")
for f in FAILS:
    print(" *", f)
sys.exit(1 if FAILS else 0)
