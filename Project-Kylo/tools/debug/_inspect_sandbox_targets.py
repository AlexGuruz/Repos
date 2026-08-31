"""Inspect sandbox rules Target Sheet usage + existing headers on target tabs."""
from __future__ import annotations

from collections import Counter, defaultdict

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def get(rng: str):
    return (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption="UNFORMATTED_VALUE")
        .execute()
        .get("values", [])
    )


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


meta = svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute()
tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
print("TABS:", tabs)

for rules_tab in ["TRANSACTIONS RULES", "BANK RULES"]:
    rows = get(a1(rules_tab, "A1:I300"))
    hdr = [str(c).strip() for c in rows[0]] if rows else []
    print(f"\n=== {rules_tab} headers ===", hdr)
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    sheet_i = idx.get("TARGET SHEET", idx.get("TARGET_SHEET", 1))
    header_i = idx.get("TARGET HEADER", idx.get("TARGET_HEADER", 2))
    by_sheet = Counter()
    by_sheet_header = defaultdict(set)
    for r in rows[1:]:
        if not r:
            continue
        sheet = str(r[sheet_i]).strip() if len(r) > sheet_i else ""
        header = str(r[header_i]).strip() if len(r) > header_i else ""
        if not sheet:
            continue
        by_sheet[sheet] += 1
        by_sheet_header[sheet].add(header)
    print("Target sheets:", dict(by_sheet))
    for sh, headers in sorted(by_sheet_header.items()):
        print(f"  {sh}: {sorted(h for h in headers if h)}")

for tab in ["JGD EXPENSES", "JGD", "PAYROLL", "NUGZ COG", "CC Payments", "ALLOCATED", "NON CANNABIS", "INCOME", "BALANCE"]:
    if tab not in tabs:
        print(f"\nMISSING TAB: {tab}")
        continue
    r19 = get(a1(tab, "A19:BZ19"))
    headers = [str(c).strip() for c in (r19[0] if r19 else [])]
    nonempty = [h for h in headers if h]
    print(f"\n{tab} row19 ({len(nonempty)} headers): {nonempty}")

print("\nBALANCE values A19:L22:")
for row in get(a1("BALANCE", "A19:L22")):
    print(row)
print("\nBALANCE formulas A20:L22:")
resp = (
    svc.spreadsheets()
    .values()
    .get(spreadsheetId=SID, range=a1("BALANCE", "A20:L22"), valueRenderOption="FORMULA")
    .execute()
    .get("values", [])
)
for row in resp:
    print(row)
