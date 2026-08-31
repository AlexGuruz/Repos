"""Spot-check sandbox INCOME/BALANCE layout after dual-rule post."""
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
        .get(spreadsheetId=SID, range=rng, valueRenderOption="FORMATTED_VALUE")
        .execute()
        .get("values", [])
    )


print("INCOME row18:", get("'INCOME'!A18:U18"))
print("INCOME row19:", get("'INCOME'!A19:U19"))
print("INCOME row20:", get("'INCOME'!A20:U20"))
print("BALANCE row18:", get("'BALANCE'!A18:L18"))
print("BALANCE row19 I-L:", get("'BALANCE'!I19:L19"))
print("BALANCE row20 I-L:", get("'BALANCE'!I20:L20"))
# sample SQUARE (bank) col M and REG 1 (cash) col C on a day with data
print("INCOME C20 (REG1), M20 (SQUARE), T20 (FROM BANK):", get("'INCOME'!C20"), get("'INCOME'!M20"), get("'INCOME'!T20"))
