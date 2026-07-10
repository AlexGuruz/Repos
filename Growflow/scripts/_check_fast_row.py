import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from lib.projection_dashboard_config import DEFAULT_SPREADSHEET_ID  # noqa: E402
from lib.stashbox_sheets_auth import sheets_service  # noqa: E402

svc = sheets_service(None)
sid = DEFAULT_SPREADSHEET_ID
for vr in (
    svc.spreadsheets()
    .values()
    .batchGet(
        spreadsheetId=sid,
        ranges=[
            "'dashboard_data'!A56:H60",
            "'dashboard_data'!A324:H326",
            "'dashboard_data'!A80:H84",
        ],
        majorDimension="ROWS",
        valueRenderOption="UNFORMATTED_VALUE",
    )
    .execute()
    .get("valueRanges", [])
):
    print("---")
    print("values", vr.get("values"))
