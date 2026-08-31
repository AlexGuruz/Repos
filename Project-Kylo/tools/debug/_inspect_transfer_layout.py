"""Inspect transfer-related headers and sample values on sandbox."""
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

for tab in ("INCOME", "JGD"):
    h = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=f"'{tab}'!A18:AZ19")
        .execute()
        .get("values", [])
    )
    print("===", tab, "===")
    for i, row in enumerate(h):
        print("r", 18 + i, list(enumerate(row)))

# Rules containing transfer keywords
keys = (
    "TO BANK",
    "FROM BANK",
    "DEPOSIT",
    "WITHDRAW",
    "ATM LOAD",
    "SWITCH",
    "CITIZENS",
    "CASH",
)
for rules in ("TRANSACTIONS RULES", "BANK RULES"):
    rows = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=f"'{rules}'!A1:D400")
        .execute()
        .get("values", [])
    )
    print("===", rules, "transfer-ish ===")
    for r in rows[1:]:
        src = str(r[0] if r else "").upper()
        if any(k in src for k in keys):
            print(r[:4])
