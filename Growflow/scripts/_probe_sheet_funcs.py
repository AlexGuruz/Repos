from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID
from lib.stashbox_sheets_auth import sheets_service

s = sheets_service(None)
for rng in ("'dashboard_data'!AC10", "'dashboard_data'!AC13", "'dashboard_data'!AC14"):
    r = (
        s.spreadsheets()
        .values()
        .get(
            spreadsheetId=DEFAULT_SPREADSHEET_ID,
            range=rng,
            valueRenderOption="UNFORMATTED_VALUE",
        )
        .execute()
    )
    print(rng, (r.get("values") or [[None]])[0][0])
