"""Set clean simple headers on BALANCE row 19; clear verbose row 18 and orphan cols E-H."""
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
svc = build(
    "sheets",
    "v4",
    credentials=service_account.Credentials.from_service_account_file(
        SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    ),
    cache_discovery=False,
)

# Clean, simple single-row headers (row 19)
headers = [
    "Day",        # A  weekday
    "Date",       # B
    "Cash Net",   # C  daily cash change
    "Bank Net",   # D  daily bank change
    "",           # E  (orphaned)
    "",           # F  (orphaned)
    "",           # G  (orphaned)
    "",           # H  (orphaned)
    "Bank EOD",   # I
    "Cash EOD",   # J
    "In Transit", # K
    "Available",  # L
]

# Clear verbose row 18 labels
svc.spreadsheets().values().update(
    spreadsheetId=SID,
    range="BALANCE!A18:L18",
    valueInputOption="RAW",
    body={"values": [[""] * 12]},
).execute()
time.sleep(1)

# Write clean row 19 headers
svc.spreadsheets().values().update(
    spreadsheetId=SID,
    range="BALANCE!A19:L19",
    valueInputOption="RAW",
    body={"values": [headers]},
).execute()
time.sleep(1)

# Clear orphaned data columns E-H for all day rows (old reconstruction breakdown)
svc.spreadsheets().values().clear(
    spreadsheetId=SID,
    range="BALANCE!E20:H400",
).execute()

print("BALANCE clean headers set on row 19; row 18 and orphan cols E-H cleared.")

# Read back
v = (
    svc.spreadsheets()
    .values()
    .get(spreadsheetId=SID, range="BALANCE!A19:L21", valueRenderOption="FORMATTED_VALUE")
    .execute()
    .get("values", [])
)
for i, r in enumerate(v):
    print(19 + i, r)
