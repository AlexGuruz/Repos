"""Peek rules headers for JGD/INCOME and sample projection days (sandbox)."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def get(rng, render="FORMATTED_VALUE"):
    for i in range(10):
        try:
            return (
                svc.spreadsheets()
                .values()
                .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
                .execute()
                .get("values", [])
            )
        except HttpError as e:
            if getattr(e, "resp", None) and e.resp.status in (429, 503):
                time.sleep(25 + i * 12)
                continue
            raise
    return []


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


def rules(tab, sheets):
    rows = get(f"'{tab}'!A1:I400")
    if not rows:
        return []
    hdr = [str(c).strip().upper() for c in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    si, hi = idx.get("TARGET SHEET", 1), idx.get("TARGET HEADER", 2)
    out = []
    for r in rows[1:]:
        if len(r) <= max(si, hi):
            continue
        ts = str(r[si]).strip()
        if ts.upper() in sheets:
            out.append((ts, str(r[hi]).strip()))
    return out


print("=== JGD rules ===")
for pair in rules("TRANSACTIONS RULES", {"JGD", "CASH JGD"}) + rules(
    "BANK RULES", {"JGD", "BANK JGD"}
):
    print(" ", pair)

print("\n=== INCOME Z-AC sample (headers + 3 days) ===")
print(get("'INCOME'!Z19:AC22"))

print("\n=== BALANCE headers + D0 region ===")
print("18-19:", get("'BALANCE'!A18:L19"))
# find recent actuals via unformatted
spine = get("'BALANCE'!B20:L400", "UNFORMATTED_VALUE")
# print last non-empty G or look near today
from datetime import date as ddate

today = ddate(2026, 7, 17)
hits = []
for i, r in enumerate(spine):
    if not r:
        continue
    d = parse_date(r[0] if r else None)
    if d and d >= ddate(2026, 7, 10):
        # B=date idx0, ... G=idx5, H=6, I=7, J=8, K=9, L=10
        hits.append((20 + i, d, r))
for h in hits[:25]:
    print(h[0], h[1], "G/H/I/J/K/L=", h[2][5:11] if len(h[2]) > 5 else h[2])
