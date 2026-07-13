"""
Google Sheets API helper.

Auth (first match wins):
  GOOGLE_APPLICATION_CREDENTIALS — service account JSON (preferred for scheduled runs)
  GOOGLE_CREDENTIALS_FILE — OAuth desktop client JSON (installed app)
  GOOGLE_SHEETS_TOKEN_FILE — OAuth token path (default: token.sheets.json next to credentials)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from google_auth_oauthlib.flow import InstalledAppFlow

SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

_ADAPTER_ROOT = Path(__file__).resolve().parents[1] / "email_sorter" / "gmail_portable"
_LEGACY_CREDENTIALS_FILE = _ADAPTER_ROOT / "credentials.json"
_LEGACY_TOKEN_FILE = _ADAPTER_ROOT / "token.sheets.json"


def _resolve_env_path(value: str | None) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = _ADAPTER_ROOT / p
    return p


def _credentials_path() -> Path | None:
    for p in (
        _resolve_env_path(os.getenv("GOOGLE_CREDENTIALS_FILE")),
        _LEGACY_CREDENTIALS_FILE,
    ):
        if p and p.is_file():
            return p
    return None


def _service_account_path() -> Path | None:
    p = _resolve_env_path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
    if p and p.is_file():
        return p
    return None


def _sheets_token_path(credentials_file: Path) -> Path:
    env = _resolve_env_path(os.getenv("GOOGLE_SHEETS_TOKEN_FILE"))
    if env:
        return env
    return credentials_file.parent / "token.sheets.json"


def preflight_sheets_auth() -> dict[str, Any]:
    svc = _service_account_path()
    cred = _credentials_path()
    tok = _sheets_token_path(cred) if cred else _LEGACY_TOKEN_FILE
    return {
        "ok": bool(svc and svc.is_file()) or bool(cred and cred.is_file()) or tok.is_file(),
        "service_account_file": str(svc) if svc else None,
        "credentials_file": str(cred) if cred else None,
        "sheets_token_file": str(tok),
        "token_exists": tok.is_file(),
    }


def get_sheets_service() -> Resource:
    service_account_file = _service_account_path()
    if service_account_file:
        creds = service_account.Credentials.from_service_account_file(
            str(service_account_file),
            scopes=SHEETS_SCOPES,
        )
        return build("sheets", "v4", credentials=creds, cache_discovery=False)

    credentials_file = _credentials_path()
    if not credentials_file:
        raise FileNotFoundError(
            "Google Sheets auth not found. Set GOOGLE_APPLICATION_CREDENTIALS (service account) or "
            f"GOOGLE_CREDENTIALS_FILE (OAuth) — see config/bank_vendor_cleaner/settings.example.env"
        )
    token_file = _sheets_token_path(credentials_file)
    creds: Credentials | None = None
    if token_file.is_file():
        creds = Credentials.from_authorized_user_file(str(token_file), SHEETS_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SHEETS_SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _column_letter_to_index(column: str) -> int:
    col = (column or "C").strip().upper()
    idx = 0
    for ch in col:
        if not ch.isalpha():
            continue
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return max(1, idx)


def read_column_values(
    service: Resource,
    spreadsheet_id: str,
    sheet_name: str,
    column: str,
    start_row: int,
) -> list[str]:
    col = (column or "C").strip().upper()
    range_name = f"'{sheet_name}'!{col}{start_row}:{col}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name, majorDimension="COLUMNS")
        .execute()
    )
    values = result.get("values") or []
    if not values:
        return []
    col_values = values[0] if isinstance(values[0], list) else values
    return [str(v) if v is not None else "" for v in col_values]


def read_range_values(
    service: Resource,
    spreadsheet_id: str,
    sheet_name: str,
    a1_range: str,
) -> list[list[str]]:
    range_name = f"'{sheet_name}'!{a1_range}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    rows = result.get("values") or []
    return [[str(c) if c is not None else "" for c in row] for row in rows]


def write_column_values(
    service: Resource,
    spreadsheet_id: str,
    sheet_name: str,
    column: str,
    start_row: int,
    values: list[str],
) -> int:
    if not values:
        return 0
    col = (column or "C").strip().upper()
    end_row = start_row + len(values) - 1
    range_name = f"'{sheet_name}'!{col}{start_row}:{col}{end_row}"
    body = {"values": [[v] for v in values], "majorDimension": "ROWS"}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body,
    ).execute()
    return len(values)


def detect_formula_cells_in_range(
    service: Resource,
    spreadsheet_id: str,
    sheet_name: str,
    a1_range: str,
) -> list[str]:
    """Return A1 addresses of cells whose user-entered value is a formula."""
    range_name = f"'{sheet_name}'!{a1_range}"
    resp = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            ranges=[range_name],
            includeGridData=True,
            fields="sheets(data(rowData(values(userEnteredValue))))",
        )
        .execute()
    )
    hits: list[str] = []
    sheets = resp.get("sheets") or []
    for sheet in sheets:
        for block in sheet.get("data") or []:
            start_row = (block.get("startRow") or 0) + 1
            start_col = block.get("startColumn") or 0
            for r_idx, row in enumerate(block.get("rowData") or []):
                for c_idx, cell in enumerate((row or {}).get("values") or []):
                    uev = (cell or {}).get("userEnteredValue") or {}
                    if "formulaValue" in uev:
                        row_num = start_row + r_idx
                        col_letter = chr(ord("A") + start_col + c_idx)
                        hits.append(f"{col_letter}{row_num}")
    return hits
