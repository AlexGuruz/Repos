from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID
from lib.stashbox_sheets_auth import sheets_service

s = sheets_service(None)
s.spreadsheets().values().update(
    spreadsheetId=DEFAULT_SPREADSHEET_ID,
    range="'dashboard_data'!AC10",
    valueInputOption="USER_ENTERED",
    body={"values": [['=IFERROR(1/0,"dash")']]},
).execute()

r = (
    s.spreadsheets()
    .values()
    .get(
        spreadsheetId=DEFAULT_SPREADSHEET_ID,
        range="'dashboard_data'!AC10",
        valueRenderOption="UNFORMATTED_VALUE",
    )
    .execute()
)
print(r.get("values"))
