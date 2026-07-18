"""Hide remaining merged-source twin tabs on sandbox."""
from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
EXTRA = [
    "CASH NUGZ COG",
    "CASH NON CANNABIS",
    "CASH ALLOCATED",
    "CASH CANNABIS DIST",
    "BANK CC Payments",
]
creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
meta = svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute()
tabs = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
reqs = []
for t in EXTRA:
    if t in tabs:
        reqs.append({
            "updateSheetProperties": {
                "properties": {"sheetId": tabs[t], "hidden": True},
                "fields": "hidden",
            }
        })
        print("hide", t)
if reqs:
    svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute()
print("done", len(reqs))
