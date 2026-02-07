"""Google Sheets helper for COG allocation."""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent


def get_sheets_client():
    """Return gspread client if configured. Uses device-wide creds when available."""
    try:
        import gspread
    except ImportError:
        return None
    from lib.config_loader import load_config, get_service_account_path
    creds_file = get_service_account_path()
    if not creds_file:
        return None
    cfg = load_config()
    spreadsheet_id = cfg.get("google_sheets", {}).get("spreadsheet_id")
    if not spreadsheet_id:
        return None
    gc = gspread.service_account(filename=str(creds_file))
    return gc.open_by_key(spreadsheet_id)


def get_workbook(spreadsheet_id: str):
    """Open a workbook by ID. Uses device-wide creds."""
    try:
        import gspread
    except ImportError:
        return None
    from lib.config_loader import get_service_account_path
    creds_file = get_service_account_path()
    if not creds_file:
        return None
    gc = gspread.service_account(filename=str(creds_file))
    return gc.open_by_key(spreadsheet_id)


def append_to_cog_raw_daily(rows: list) -> bool:
    """Append rows to COG_RAW_DAILY sheet. Columns: Date, Brand, Category, Units, COG."""
    from lib.config_loader import load_config
    cfg = load_config()
    t = cfg.get("google_sheets", {}).get("cog_raw_daily", {})
    sid, sheet = t.get("spreadsheet_id"), t.get("sheet", "COG_RAW_DAILY")
    if not sid:
        return False
    sh = get_workbook(sid)
    if not sh:
        return False
    ws = sh.worksheet(sheet)
    ws.append_rows(rows, value_input_option="USER_ENTERED")
    return True


def append_to_pos_export(rows: list) -> bool:
    """Append rows to POS_Export sheet. Columns: Date, Product Name, ProductCategory, Brand, NetPrice, COGS."""
    from lib.config_loader import load_config
    cfg = load_config()
    t = cfg.get("google_sheets", {}).get("pos_export", {})
    sid, sheet = t.get("spreadsheet_id"), t.get("sheet", "POS_Export")
    if not sid:
        return False
    sh = get_workbook(sid)
    if not sh:
        return False
    ws = sh.worksheet(sheet)
    for row in rows:
        ws.append_row(row, value_input_option="USER_ENTERED")
    return True


def write_brands_to_drop_down_helper(brands: list) -> bool:
    """Write unique brands to DROP DOWN HELPER column E."""
    sh = get_sheets_client()
    if not sh:
        return False
    from lib.config_loader import load_config
    cfg = load_config()
    sheet_name = cfg.get("google_sheets", {}).get("drop_down_helper_sheet", "DROP DOWN HELPER")
    ws = sh.worksheet(sheet_name)
    for i, b in enumerate(sorted(brands), start=1):
        ws.update_acell(f"E{i}", b)
    return True
