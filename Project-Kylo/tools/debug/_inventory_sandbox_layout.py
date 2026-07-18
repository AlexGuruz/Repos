"""Inventory current sandbox target-tab headers (SANDBOX ONLY)."""
from __future__ import annotations

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

TABS = [
    "PAYROLL",
    "JGD",
    "INCOME",
    "CASH EXPENSES",
    "BANK EXPENSES",
    "NUGZ COG",
    "CC Payments",
    "NON CANNABIS",
    "ALLOCATED",
    "CANNABIS DIST",
    "BALANCE",
]


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


meta = svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute()
print("=== ALL TABS ===")
for s in meta["sheets"]:
    p = s["properties"]
    hidden = p.get("hidden", False)
    flag = "[H]" if hidden else "   "
    print(f"  {flag} {p['title']!r} id={p['sheetId']}")

for tab in TABS:
    for row in (1, 18, 19, 20):
        rng = a1(tab, f"A{row}:BZ{row}")
        try:
            vals = (
                svc.spreadsheets()
                .values()
                .get(
                    spreadsheetId=SID,
                    range=rng,
                    valueRenderOption="FORMATTED_VALUE",
                )
                .execute()
                .get("values", [])
            )
        except Exception as e:
            print(f"{tab} row{row}: ERR {e}")
            continue
        rowv = vals[0] if vals else []
        nonempty = [(col_letter(i + 1), c) for i, c in enumerate(rowv) if str(c).strip()]
        print(f"\n=== {tab} row {row} ({len(nonempty)} nonempty) ===")
        for cl, c in nonempty:
            print(f"  {cl}: {c!r}")
