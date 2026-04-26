"""Shared defaults for projection → Google Sheets capital dashboard."""

import os

from lib.dashboard_sheets_env import load_dashboard_sheets_env_file

load_dashboard_sheets_env_file()

# Env ``PROJECTION_DASHBOARD_SPREADSHEET_ID`` overrides (set in config/dashboard_sheets.env).
DEFAULT_SPREADSHEET_ID = (
    os.environ.get("PROJECTION_DASHBOARD_SPREADSHEET_ID", "").strip()
    or "17sqC9JOMMLEWZhd5S_t9FUkZJpKYSqtblBeKs8WCz7U"
)
