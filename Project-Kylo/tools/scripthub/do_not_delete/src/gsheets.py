from __future__ import annotations

import json
import re
import string
from pathlib import Path
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def load_cfg(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def svc_from_sa(sa_path: str):
    creds = Credentials.from_service_account_file(
        sa_path, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds)


def col_to_a1(c: int) -> str:
    s = ""
    while c:
        c, r = divmod(c - 1, 26)
        s = string.ascii_uppercase[r] + s
    return s


def a1(tab: str, r1: int, c1: int, r2: int, c2: int) -> str:
    return f"{tab}!{col_to_a1(c1)}{r1}:{col_to_a1(c2)}{r2}"


def get_sheet_id(svc, spreadsheet_id: str, tab: str) -> int:
    meta = svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == tab:
            return s["properties"]["sheetId"]
    raise ValueError(f"Sheet '{tab}' not found")


def norm(text: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(text or "").upper()).strip()


def ensure_id(value: str) -> str:
    """Return spreadsheet ID given an ID or a full Sheets URL.

    Accepts either the raw ID or URLs like
    https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0
    """
    if "/d/" in value:
        try:
            part = value.split("/d/")[1]
            return part.split("/")[0]
        except Exception:
            return value
    return value
