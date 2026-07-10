from lib.stashbox_sheets_auth import sheets_service
from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID

s = sheets_service(None)
sid = DEFAULT_SPREADSHEET_ID
for rng in [
    "dashboard_data!A2500",
    "dashboard_data!AC3",
    "dashboard_data!AB3",
    "dashboard_data!AD3",
]:
    r = (
        s.spreadsheets()
        .values()
        .get(spreadsheetId=sid, range=rng, valueRenderOption="FORMULA")
        .execute()
    )
    print(rng, r.get("values"))
