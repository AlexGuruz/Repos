from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID
from lib.stashbox_sheets_auth import sheets_service

s = sheets_service(None)
s.spreadsheets().values().update(
    spreadsheetId=DEFAULT_SPREADSHEET_ID,
    range="'dashboard_data'!AC10",
    valueInputOption="USER_ENTERED",
    body={"values": [["=2+2"]]},
).execute()
print("AC10 := 2+2")
