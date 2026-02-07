from __future__ import annotations

from typing import Any, Dict, List, Tuple
from hashlib import md5

import os
import re

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from services.common.config_loader import load_config
from services.common.retry import google_api_execute


def build_batch_update(changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a single spreadsheets.batchUpdate payload body.

    The sorting module will construct "requests" entries; this function only wraps them.
    """
    return {"requests": changes or []}


class SheetsPoster:
    def __init__(self, *, dry_run: bool | None = None, quota_budget: int | None = None):
        if dry_run is None:
            # If explicitly set, env always wins (tests + ops overrides).
            env_raw = os.environ.get("KYLO_SHEETS_DRY_RUN")
            if env_raw is not None:
                env_val = str(env_raw).lower()
                dry_run = env_val in ("1", "true", "yes", "y")
            else:
                # Prefer YAML posting.sheets.apply=false -> dry_run True
                try:
                    cfg = load_config()
                    apply = bool(cfg.get("posting.sheets.apply", False))
                    dry_run = not apply
                except Exception:
                    # Safe default if config can't be loaded
                    dry_run = True
        if quota_budget is None:
            quota_budget = int(os.environ.get("KYLO_SHEETS_QUOTA_BUDGET", "0"))
        self.dry_run = bool(dry_run)
        self.quota_budget = int(quota_budget)

    def build_batch_update(self, spreadsheet_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"spreadsheetId": spreadsheet_id, "requests": ops}

    def post(self, spreadsheet_id: str, ops: List[Dict[str, Any]]) -> Dict[str, Any]:
        body = self.build_batch_update(spreadsheet_id, ops)
        return {"dry_run": self.dry_run, "body": body}


# ===== New helpers for spreadsheet/tab setup =====


def _get_service() -> Any:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    # Prefer explicit env; else consult YAML config; else repo default
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not sa_path:
        try:
            cfg = load_config()
            sa_path = cfg.get("google.service_account_json_path")
        except Exception:
            sa_path = None
    if not sa_path:
        sa_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "secrets", "service_account.json")
    creds = Credentials.from_service_account_file(sa_path, scopes=scopes)
    return build("sheets", "v4", credentials=creds)


def _extract_spreadsheet_id(value: str) -> str:
    if "/spreadsheets/d/" in value:
        try:
            return value.split("/spreadsheets/d/")[1].split("/")[0]
        except Exception:
            return value
    return value


def ensure_spreadsheet(spreadsheet_id_or_name: str) -> str:
    """
    If the argument is an ID or URL to an existing spreadsheet, return its ID.
    Otherwise create a new spreadsheet with the given title and return the new ID.
    """
    service = _get_service()
    candidate = _extract_spreadsheet_id(spreadsheet_id_or_name)
    # Heuristic: if it looks like an ID (no spaces, length > 20), try GET
    looks_like_id = (" " not in candidate) and (len(candidate) >= 20)
    if looks_like_id:
        try:
            req = service.spreadsheets().get(spreadsheetId=candidate, fields="spreadsheetId")
            _ = google_api_execute(req, label="sheets:get")
            return candidate
        except Exception:
            # Fall back to creating by title
            pass
    body = {"properties": {"title": spreadsheet_id_or_name}}
    created = google_api_execute(service.spreadsheets().create(body=body), label="sheets:create")
    return created.get("spreadsheetId")


def _fetch_meta(service, spreadsheet_id: str) -> Tuple[Dict[str, int], List[int]]:
    meta = google_api_execute(service.spreadsheets().get(spreadsheetId=spreadsheet_id), label="sheets:meta")
    titles_to_ids: Dict[str, int] = {}
    existing_ids: List[int] = []
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        sid = int(props.get("sheetId"))
        title = props.get("title")
        titles_to_ids[title] = sid
        existing_ids.append(sid)
    return titles_to_ids, existing_ids


def _generate_unique_sheet_id(existing_ids: List[int]) -> int:
    # Use stable offset approach to avoid collisions
    base = max(existing_ids or [0]) + 1
    # Ensure within 32-bit
    return base if base < 2_147_000_000 else 1_000_000


def _approved_col_index(headers: List[str]) -> int:
    for i, h in enumerate(headers):
        if str(h).strip().lower() == "approved":
            return i
    return -1


def apply_headers_and_format(
    spreadsheet_id: str,
    company_id: str,
    pending_headers: List[str],
    active_headers: List[str],
    theme_spec: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build requests to ensure tabs for a company, set headers on row 1,
    apply validation and dark theme formatting. Does not execute.
    """
    service = _get_service()
    titles_to_ids, existing_ids = _fetch_meta(service, spreadsheet_id)

    # Use the new tab naming convention: "{company_id} Pending" and "{company_id} Active"
    pending_title = f"{company_id} Pending"
    active_title = f"{company_id} Active"
    pending_id = titles_to_ids.get(pending_title)
    active_id = titles_to_ids.get(active_title)

    requests: List[Dict[str, Any]] = []

    # Add missing sheets with explicit ids so later requests can reference them in same batch
    if pending_id is None:
        pending_id = _generate_unique_sheet_id(existing_ids)
        existing_ids.append(pending_id)
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": pending_id,
                        "title": pending_title,
                        "gridProperties": {"frozenRowCount": 1, "rowCount": 2000, "columnCount": max(len(pending_headers), 11)},
                    }
                }
            }
        )
    if active_id is None:
        active_id = _generate_unique_sheet_id(existing_ids)
        existing_ids.append(active_id)
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": active_id,
                        "title": active_title,
                        "gridProperties": {"frozenRowCount": 1, "rowCount": 2000, "columnCount": max(len(active_headers), 8)},
                    }
                }
            }
        )

    # Freeze header row on both (even if existing)
    requests.extend(
        [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": pending_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": active_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
    )

    # Write headers (row 1)
    def _row(values: List[Any]) -> Dict[str, Any]:
        return {"values": [{"userEnteredValue": {"stringValue": str(v)}} for v in values]}

    requests.extend(
        [
            {
                "updateCells": {
                    "range": {"sheetId": pending_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(pending_headers)},
                    "fields": "userEnteredValue",
                    "rows": [_row(pending_headers)],
                }
            },
            {
                "updateCells": {
                    "range": {"sheetId": active_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(active_headers)},
                    "fields": "userEnteredValue",
                    "rows": [_row(active_headers)],
                }
            },
        ]
    )

    # Data validation: Approved column in Pending
    appr_idx = _approved_col_index(pending_headers)
    if appr_idx >= 0:
        requests.append(
            {
                "setDataValidation": {
                    "range": {"sheetId": pending_id, "startRowIndex": 1, "startColumnIndex": appr_idx, "endColumnIndex": appr_idx + 1},
                    "rule": {
                        "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "TRUE"}, {"userEnteredValue": "FALSE"}]},
                        "strict": True,
                        "inputMessage": "Select TRUE to approve, FALSE to hold",
                    },
                }
            }
        )

    # Dark theme styling
    header_fmt = {
        "userEnteredFormat": {
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
        }
    }
    body_fmt = {
        "userEnteredFormat": {
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
        }
    }
    tab_color = theme_spec.get("tabColor", {"red": 0.4, "green": 0.0, "blue": 0.6})

    requests.extend(
        [
            {"repeatCell": {"range": {"sheetId": pending_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": header_fmt, "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
            {"repeatCell": {"range": {"sheetId": active_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": header_fmt, "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
            {"repeatCell": {"range": {"sheetId": pending_id, "startRowIndex": 1}, "cell": body_fmt, "fields": "userEnteredFormat(textFormat.foregroundColor,backgroundColor)"}},
            {"repeatCell": {"range": {"sheetId": active_id, "startRowIndex": 1}, "cell": body_fmt, "fields": "userEnteredFormat(textFormat.foregroundColor,backgroundColor)"}},
            {"updateSheetProperties": {"properties": {"sheetId": pending_id, "tabColor": tab_color}, "fields": "tabColor"}},
            {"updateSheetProperties": {"properties": {"sheetId": active_id, "tabColor": tab_color}, "fields": "tabColor"}},
        ]
    )

    return requests


def ensure_company_tabs(spreadsheet_id: str, company_ids: List[str]) -> Dict[str, Any]:
    """
    Build one batchUpdate payload covering all companies.
    Does not execute; returns {"requests": [...]}.
    """
    pending_headers = ["Date", "Source", "Company", "Amount", "Target_Sheet", "Target_Header", "Approved"]
    active_headers = ["Ruleset_Version", "Effective_At", "Company_ID", "Source", "Target_Sheet", "Target_Header", "Match_Notes", "Created_At"]
    theme_spec = {"tabColor": {"red": 0.4, "green": 0.0, "blue": 0.6}}

    all_reqs: List[Dict[str, Any]] = []
    for cid in company_ids:
        all_reqs.extend(apply_headers_and_format(spreadsheet_id, cid, pending_headers, active_headers, theme_spec))
    return {"requests": all_reqs}


# ===== Constants per spec =====

HEADERS = [
    "date",
    "source",
    "company",
    "amount",
    "target_sheet",
    "target_header",
    "approved",
]
APPROVED_COL_INDEX = 6  # zero-based (G)
HEADER_RANGE = "A1:G1"


def build_tab_name(cid: str, kind: "Literal['Active','Pending']") -> str:
    return f"{cid} {kind}"


def ensure_company_tabs_minimal(spreadsheet_id: str, cids: List[str]) -> List[Dict[str, Any]]:
    """Emit addSheet requests only when missing, using tab names "{CID} Active" and "{CID} Pending".
    Returns list of requests (not executed)."""
    service = _get_service()
    titles_to_ids, existing_ids = _fetch_meta(service, spreadsheet_id)
    reqs: List[Dict[str, Any]] = []
    for cid in cids:
        for kind in ("Active", "Pending"):
            title = build_tab_name(cid, kind)  # e.g., "710 Active"
            if title in titles_to_ids:
                continue
            new_id = _generate_unique_sheet_id(existing_ids)
            existing_ids.append(new_id)
            reqs.append(
                {
                    "addSheet": {
                        "properties": {
                            "sheetId": new_id,
                            "title": title,
                            "gridProperties": {"frozenRowCount": 1, "rowCount": 2000, "columnCount": len(HEADERS)},
                        }
                    }
                }
            )
    return reqs


def header_requests(tab_id: int, headers: List[str]) -> List[Dict[str, Any]]:
    def _row(values: List[Any]) -> Dict[str, Any]:
        return {"values": [{"userEnteredValue": {"stringValue": str(v)}} for v in values]}

    return [
        # Write header values (A1:G1)
        {
            "updateCells": {
                "range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": len(headers)},
                "fields": "userEnteredValue",
                "rows": [_row(headers)],
            }
        },
        # Freeze header row
        {
            "updateSheetProperties": {
                "properties": {"sheetId": tab_id, "gridProperties": {"frozenRowCount": 1}},
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]


def validation_requests(tab_id: int) -> List[Dict[str, Any]]:
    return [
        {
            "setDataValidation": {
                "range": {"sheetId": tab_id, "startRowIndex": 1, "startColumnIndex": APPROVED_COL_INDEX, "endColumnIndex": APPROVED_COL_INDEX + 1},
                "rule": {
                    "condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "TRUE"}, {"userEnteredValue": "FALSE"}]},
                    "strict": True,
                    "inputMessage": "Select TRUE to approve, FALSE to hold",
                },
            }
        }
    ]


def theme_requests(tab_id: int) -> List[Dict[str, Any]]:
    header_fmt = {
        "userEnteredFormat": {
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
        }
    }
    body_fmt = {
        "userEnteredFormat": {
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}},
            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
        }
    }
    tab_color = {"red": 0.6, "green": 0.0, "blue": 0.2}  # purple/red accent
    return [
        {"repeatCell": {"range": {"sheetId": tab_id, "startRowIndex": 0, "endRowIndex": 1}, "cell": header_fmt, "fields": "userEnteredFormat(textFormat,backgroundColor)"}},
        {"repeatCell": {"range": {"sheetId": tab_id, "startRowIndex": 1}, "cell": body_fmt, "fields": "userEnteredFormat(textFormat.foregroundColor,backgroundColor)"}},
        {"updateSheetProperties": {"properties": {"sheetId": tab_id, "tabColor": tab_color}, "fields": "tabColor"}},
    ]


def build_headers_batch(spreadsheet_id: str, cids: List[str], headers: List[str] | None = None) -> Dict[str, Any]:
    """Compose a single batchUpdate body to add missing sheets, write headers, freeze, validation, and theme.
    Uses tab names "{CID} Active" and "{CID} Pending".
    """
    headers = headers or HEADERS
    service = _get_service()
    titles_to_ids, existing_ids = _fetch_meta(service, spreadsheet_id)

    requests: List[Dict[str, Any]] = []

    # Step 1: add missing sheets (assign explicit ids)
    for cid in cids:
        for kind in ("Active", "Pending"):
            title = build_tab_name(cid, kind)
            if title not in titles_to_ids:
                new_id = _generate_unique_sheet_id(existing_ids)
                existing_ids.append(new_id)
                titles_to_ids[title] = new_id
                requests.append(
                    {
                        "addSheet": {
                            "properties": {
                                "sheetId": new_id,
                                "title": title,
                                "gridProperties": {"frozenRowCount": 1, "rowCount": 2000, "columnCount": len(headers)},
                            }
                        }
                    }
                )

    # Step 2: header, validation, theme for each tab
    for cid in cids:
        for kind in ("Active", "Pending"):
            tab_title = build_tab_name(cid, kind)
            tab_id = titles_to_ids.get(tab_title)
            if tab_id is None:
                continue
            # Use the same 7-field HEADERS for both Active and Pending per spec
            requests.extend(header_requests(tab_id, headers))
            # Apply TRUE/FALSE validation to Approved column on both tabs
            requests.extend(validation_requests(tab_id))
            requests.extend(theme_requests(tab_id))

    return {"requests": requests}


# ===== Pending mode helpers =====

PENDING_HEADERS = ["txn_uid","date","description","amount","target_sheet","target_header","approved"]

def build_pending_rows(pending_items: List[Dict]) -> List[Dict]:
    """
    pending_items: [{txn_uid, date(str YYYY-MM-DD), description, amount(float/str), target_sheet, target_header, approved(False)}, ...]
    Returns Sheets 'rows' (for appendCells).
    """
    rows = []
    for it in pending_items:
        values = [
            {"userEnteredValue": {"stringValue": it["txn_uid"]}},
            {"userEnteredValue": {"stringValue": it["date"]}},
            {"userEnteredValue": {"stringValue": it["description"]}},
            {"userEnteredValue": {"numberValue": float(it["amount"]) }},
            {"userEnteredValue": {"stringValue": it.get("target_sheet","")}},
            {"userEnteredValue": {"stringValue": it.get("target_header","")}},
            {"userEnteredValue": {"boolValue": bool(it.get("approved", False))}},
        ]
        rows.append({"values": values})
    return rows

def build_pending_batch_update(sheet_id: int, rows: List[Dict]) -> Dict:
    """
    Returns a Google Sheets batchUpdate payload that:
      - freezes header row 1
      - ensures data validation on column G (approved)
      - appends provided rows
    Caller is responsible for resolving sheet_id and ensuring headers exist.
    """
    return {
        "requests": [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "setDataValidation": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 1,
                        "startColumnIndex": 6,  # G (0-based)
                        "endColumnIndex": 7
                    },
                    "rule": {"condition": {"type": "BOOLEAN"}, "strict": True, "inputMessage": "Choose TRUE or FALSE"},
                }
            },
            {
                "appendCells": {
                    "sheetId": sheet_id,
                    "rows": rows,
                    "fields": "userEnteredValue"
                }
            },
        ],
        "includeSpreadsheetInResponse": False,
        "responseIncludeGridData": False,
    }

def compute_pending_batch_signature(company_id: str, tab_name: str, txn_uids: List[str], layout_version: str = "v1") -> str:
    key = company_id + "|" + tab_name + "|" + layout_version + "|" + ",".join(sorted(txn_uids))
    return md5(key.encode("utf-8")).hexdigest()

