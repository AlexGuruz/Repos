"""Fix sandbox alignment with batched Sheets I/O.

SANDBOX ONLY: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
TODAY = date(2026, 7, 15)

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def retry(fn, *a, **k):
    for i in range(10):
        try:
            return fn(*a, **k)
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status in (429, 503):
                wait = 45 + i * 15
                print(f"  rate limit, sleep {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("retries exhausted")


def get(rng: str, render: str = "UNFORMATTED_VALUE") -> List[List[Any]]:
    def _():
        return (
            svc.spreadsheets()
            .values()
            .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
            .execute()
            .get("values", [])
        )

    return retry(_)


def update(rng: str, values: List[List[Any]], raw: bool = False) -> None:
    def _():
        svc.spreadsheets().values().update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW" if raw else "USER_ENTERED",
            body={"values": values},
        ).execute()

    retry(_)


def batch_update(data: List[Dict[str, Any]]) -> None:
    if not data:
        return

    def _():
        svc.spreadsheets().values().batchUpdate(
            spreadsheetId=SID,
            body={"valueInputOption": "USER_ENTERED", "data": data},
        ).execute()

    retry(_)


def col_letter(n1: int) -> str:
    s = ""
    n = n1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_date(v: Any) -> Optional[date]:
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


def headers_of(tab: str) -> List[str]:
    rows = get(a1(tab, "A19:BZ19"))
    if not rows:
        return []
    return [str(c).strip() if c is not None else "" for c in rows[0]]


def ensure_headers(tab: str, needed: List[str]) -> List[str]:
    headers = headers_of(tab)
    existing = {h.upper(): i for i, h in enumerate(headers) if h}
    added = []
    for h in needed:
        if not h:
            continue
        if h.upper() not in existing:
            headers.append(h)
            existing[h.upper()] = len(headers) - 1
            added.append(h)
    if added:
        update(a1(tab, "A19"), [headers], raw=True)
        print(f"  {tab}: added {added}")
        time.sleep(1.5)
    else:
        print(f"  {tab}: ok ({len(existing)} headers)")
    return headers


def load_rules_need(rules_tab: str) -> Dict[str, Set[str]]:
    rows = get(a1(rules_tab, "A1:I500"))
    if not rows:
        return {}
    hdr = [str(c).strip() for c in rows[0]]
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    sheet_i = idx.get("TARGET SHEET", 1)
    header_i = idx.get("TARGET HEADER", 2)
    appr_i = idx.get("APPROVED", 3)
    out: Dict[str, Set[str]] = {}
    for r in rows[1:]:
        if not r:
            continue
        row = list(r) + [""] * 9
        ap = row[appr_i]
        if not (ap is True or str(ap).strip().upper() in ("TRUE", "1", "YES")):
            continue
        sheet = str(row[sheet_i]).strip()
        header = str(row[header_i]).strip()
        if sheet and header:
            out.setdefault(sheet, set()).add(header)
    return out


print("=== 1) Ensure all approved rule headers exist on targets ===")
need: Dict[str, Set[str]] = {}
for tab in ("TRANSACTIONS RULES", "BANK RULES"):
    for sheet, headers in load_rules_need(tab).items():
        need.setdefault(sheet, set()).update(headers)
# always force known misses
need.setdefault("INCOME", set()).update(["CASH", "CITIZENS IN/OUT"])
need.setdefault("CASH EXPENSES", set()).add("USPS")
need.setdefault("BANK EXPENSES", set()).add("USPS")
need.setdefault("CANNABIS DIST", set()).update(
    ["420 MY WAY", "RR BROS", "WALLY'S GREEN PATCH"]
)

for sheet in sorted(need.keys()):
    ensure_headers(sheet, sorted(need[sheet]))

print("=== 2) Migrate future projections: JGD EXPENSES -> BANK EXPENSES ===")
legacy = get(a1("JGD EXPENSES", "A19:BZ400"))
bank = get(a1("BANK EXPENSES", "A19:BZ400"))
if not legacy or not bank:
    raise SystemExit("missing expense grids")

leg_h = [str(c).strip() for c in legacy[0]]
bank_h = [str(c).strip() for c in bank[0]]
# grow bank matrix columns if needed
max_cols = max(len(bank_h), max((len(r) for r in bank[1:]), default=0), 60)
while len(bank_h) < max_cols:
    bank_h.append("")
bank_hmap = {h.upper(): i for i, h in enumerate(bank_h) if h}

# index bank by date
bank_by_date: Dict[date, int] = {}  # date -> index in bank[1:]
for i, r in enumerate(bank[1:]):
    d = parse_date(r[0] if r else None)
    if d:
        bank_by_date[d] = i

# Expand each bank data row to max_cols
bank_data: List[List[Any]] = []
for r in bank[1:]:
    row = list(r) + [""] * (max_cols - len(r))
    bank_data.append(row[:max_cols])

migrated = 0
skip_filled = 0
skip_no_h = 0
skip_no_d = 0
for r in legacy[1:]:
    if not r:
        continue
    d = parse_date(r[0] if r else None)
    if d is None or d <= TODAY:
        continue
    bi = bank_by_date.get(d)
    if bi is None:
        skip_no_d += 1
        continue
    # pad legacy row
    row = list(r) + [""] * (len(leg_h) - len(r))
    for ci, cell in enumerate(row):
        if ci < 2:
            continue
        if cell in (None, ""):
            continue
        try:
            amount = float(cell)
        except Exception:
            continue
        if amount == 0:
            continue
        h = leg_h[ci] if ci < len(leg_h) else ""
        if not h or h.upper() in ("DATE", "EXPENSES"):
            continue
        col = bank_hmap.get(h.upper())
        if col is None:
            # ensure header then retry
            bank_h.append(h)
            bank_hmap[h.upper()] = len(bank_h) - 1
            col = bank_hmap[h.upper()]
            # expand all bank_data rows
            for br in bank_data:
                while len(br) < len(bank_h):
                    br.append("")
            max_cols = len(bank_h)
            skip_no_h += 0
        # ensure row width
        while len(bank_data[bi]) < len(bank_h):
            bank_data[bi].append("")
        existing = bank_data[bi][col]
        has = False
        if existing not in (None, ""):
            try:
                has = float(existing) != 0
            except Exception:
                has = True
        if has:
            skip_filled += 1
            continue
        bank_data[bi][col] = amount
        migrated += 1

print(f"  migrated_cells={migrated} skip_filled={skip_filled} skip_no_date={skip_no_d}")
# Write header + full data grid (A19 + data from A20)
update(a1("BANK EXPENSES", "A19"), [bank_h], raw=True)
time.sleep(2)
# Write in row chunks to avoid payload limits
CHUNK = 80
for start in range(0, len(bank_data), CHUNK):
    chunk = bank_data[start : start + CHUNK]
    update(a1("BANK EXPENSES", f"A{20 + start}"), chunk, raw=False)
    print(f"  wrote BANK EXPENSES rows {20+start}-{20+start+len(chunk)-1}")
    time.sleep(2)

print("=== 3) Unique-ify duplicate zone headers ===")
# JGD: rename 2nd CLOVER / SERVICE FEE
jgd = headers_of("JGD")
counts: Dict[str, int] = {}
new_jgd = []
jgd_changed = False
for h in jgd:
    key = h.upper()
    counts[key] = counts.get(key, 0) + 1
    if key in ("CLOVER", "SERVICE FEE") and counts[key] > 1 and "(BANK)" not in key:
        new_jgd.append(f"{h} (BANK)")
        jgd_changed = True
    else:
        new_jgd.append(h)
if jgd_changed:
    update(a1("JGD", "A19"), [new_jgd], raw=True)
    print("  JGD headers:", new_jgd)
    time.sleep(1.5)
    # BANK RULES retarget
    rows = get(a1("BANK RULES", "A1:I100"))
    hdr = [str(c).strip() for c in rows[0]]
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    sheet_i, header_i = idx["TARGET SHEET"], idx["TARGET HEADER"]
    out = [rows[0]]
    n = 0
    for r in rows[1:]:
        row = list(r) + [""] * 9
        if str(row[sheet_i]).strip().upper() == "JGD" and str(row[header_i]).strip().upper() in (
            "CLOVER",
            "SERVICE FEE",
        ):
            row[header_i] = f"{str(row[header_i]).strip()} (BANK)"
            n += 1
        out.append(row[: len(hdr)])
    update(a1("BANK RULES", "A1"), out, raw=True)
    print(f"  BANK RULES JGD header retargets: {n}")
else:
    print("  JGD already unique or unchanged")

# INCOME: rename 2nd (N) VENMO
inc = headers_of("INCOME")
counts = {}
new_inc = []
inc_changed = False
for h in inc:
    key = h.upper()
    counts[key] = counts.get(key, 0) + 1
    if key == "(N) VENMO" and counts[key] > 1:
        new_inc.append("(N) VENMO (BANK)")
        inc_changed = True
    else:
        new_inc.append(h)
if inc_changed:
    update(a1("INCOME", "A19"), [new_inc], raw=True)
    print("  INCOME renamed 2nd (N) VENMO")
    # If BANK rules use (N) VENMO retarget to bank-named
    rows = get(a1("BANK RULES", "A1:I100"))
    hdr = [str(c).strip() for c in rows[0]]
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    sheet_i, header_i = idx["TARGET SHEET"], idx["TARGET HEADER"]
    out = [rows[0]]
    n = 0
    for r in rows[1:]:
        row = list(r) + [""] * 9
        if (
            str(row[sheet_i]).strip().upper() == "INCOME"
            and str(row[header_i]).strip().upper() == "(N) VENMO"
        ):
            row[header_i] = "(N) VENMO (BANK)"
            n += 1
        out.append(row[: len(hdr)])
    if n:
        update(a1("BANK RULES", "A1"), out, raw=True)
        print(f"  BANK RULES INCOME (N) VENMO -> (BANK): {n}")
else:
    print("  INCOME venmo ok")

# Expense duplicate MISC / PARKING METER: rename 2nd occurrence
for tab in ("CASH EXPENSES", "BANK EXPENSES"):
    h = headers_of(tab)
    counts = {}
    new_h = []
    ch = False
    for name in h:
        key = name.upper()
        counts[key] = counts.get(key, 0) + 1
        if key in ("MISC", "PARKING METER", "MJ WASTE") and counts[key] > 1:
            new_h.append(f"{name} (2)")
            ch = True
        else:
            new_h.append(name)
    if ch:
        update(a1(tab, "A19"), [new_h], raw=True)
        print(f"  {tab}: deduped duplicate headers")
        time.sleep(1.5)
    else:
        print(f"  {tab}: no dup rename")

print("=== 4) Hide still-visible over-splits if any; leave JGD EXPENSES visible as LEGACY ref ===")
# Optionally rename JGD EXPENSES for clarity
meta = retry(
    lambda: svc.spreadsheets()
    .get(spreadsheetId=SID, fields="sheets.properties")
    .execute()
)
reqs = []
for sh in meta.get("sheets", []):
    p = sh["properties"]
    title = p["title"]
    sid = p["sheetId"]
    if title == "JGD EXPENSES" and not title.endswith("(LEGACY)"):
        reqs.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sid, "title": "JGD EXPENSES (LEGACY)"},
                    "fields": "title",
                }
            }
        )
        print("  rename JGD EXPENSES -> JGD EXPENSES (LEGACY)")

if reqs:
    retry(
        lambda: svc.spreadsheets()
        .batchUpdate(spreadsheetId=SID, body={"requests": reqs})
        .execute()
    )

update(
    a1("SANDBOX README", "A80"),
    [
        ["AUDIT FIX PASS 2026-07-15"],
        ["1. All approved rule Target Headers ensured on keep-set tabs"],
        ["2. Future projections copied JGD EXPENSES -> BANK EXPENSES (empty cells only)"],
        ["3. Duplicate zone headers uniquified (JGD bank CLOVER/SERVICE FEE; INCOME venmo; expense dups)"],
        ["4. JGD EXPENSES renamed LEGACY — do not post here"],
        ["Re-post JGD+NUGZ required after this fix"],
    ],
    raw=True,
)
print("DONE")
