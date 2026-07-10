"""
Google Sheets API auth using the same **Stashbox** service-account resolution as other Growflow scripts.

Loads ``config/dashboard_sheets.env`` first (see ``lib.dashboard_sheets_env``) if present.

Resolution order (first hit wins):
1. Explicit ``cli_path`` (e.g. ``--sheets-service-account``)
2. Env ``STASHBOX_SERVICE_ACCOUNT``
3. Env ``GOOGLE_APPLICATION_CREDENTIALS``
4. ``lib.config_loader.get_google_service_account_path()`` if that module exists
5. ``E:/secrets/gcp/stashbox.json`` if the file exists
6. ``E:/secrets/gcp/sa.json`` if the file exists
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def resolve_stashbox_service_account_json(cli_path: str | None = None) -> str:
    """Return path to a service account JSON file. Raises SystemExit if none found."""
    from lib.dashboard_sheets_env import load_dashboard_sheets_env_file

    load_dashboard_sheets_env_file()
    p = (cli_path or "").strip() or os.environ.get("STASHBOX_SERVICE_ACCOUNT", "").strip() or os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS", ""
    ).strip()
    if not p:
        try:
            from lib.config_loader import get_google_service_account_path

            x = get_google_service_account_path()
            p = str(x) if x else ""
        except Exception:
            p = ""
    if not p and Path("E:/secrets/gcp/stashbox.json").exists():
        p = "E:/secrets/gcp/stashbox.json"
    if not p and Path("E:/secrets/gcp/sa.json").exists():
        p = "E:/secrets/gcp/sa.json"
    if not p or not Path(p).exists():
        raise SystemExit(
            "Stashbox / service account JSON not found. Set --sheets-service-account, "
            "STASHBOX_SERVICE_ACCOUNT, GOOGLE_APPLICATION_CREDENTIALS, or place "
            "E:/secrets/gcp/stashbox.json"
        )
    return p


def sheets_service(cli_path: str | None = None) -> Any:
    """Google Sheets API v4 service (spreadsheets scope)."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    path = resolve_stashbox_service_account_json(cli_path)
    creds = Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def docs_service(cli_path: str | None = None) -> Any:
    """Google Docs API v1 service (documents scope). Share the Doc with the service account email as Editor."""
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    path = resolve_stashbox_service_account_json(cli_path)
    creds = Credentials.from_service_account_file(
        path, scopes=["https://www.googleapis.com/auth/documents"]
    )
    return build("docs", "v1", credentials=creds)
