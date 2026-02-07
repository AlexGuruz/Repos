from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Tuple

import os
import hashlib
from telemetry.emitter import start_trace, emit

try:
    # Prefer local project deps if available
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
except Exception:  # pragma: no cover - import-time optional in dry runs/tests
    Credentials = None  # type: ignore
    build = None  # type: ignore
from services.common.config_loader import load_config


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _deterministic_sheet_id(company_id: str, kind: str) -> int:
    """Stable, high-range sheetId from company_id and kind ("Pending"|"Active").

    Keeps ids consistent across runs so subsequent requests can target the same tabs
    without pre-reading spreadsheet metadata (to satisfy one-call constraint).
    """
    # 32-bit hash, then bias into Sheets' high id space
    h = hashlib.sha1(f"{company_id}::{kind}".encode("utf-8")).digest()
    n = int.from_bytes(h[:4], "big")
    # Keep within positive int32, shift to avoid common low ids
    base = 1_000_000
    max_int = 2_147_000_000
    return base + (n % (max_int - base))


def _to_cell(value: Any) -> Dict[str, Any]:
    return {"userEnteredValue": {"stringValue": "" if value is None else str(value)}}


def _to_row(values: Iterable[Any]) -> Dict[str, Any]:
    return {"values": [_to_cell(v) for v in values]}


def _accent_color(kind: str) -> Dict[str, float]:
    # Red for Pending, Purple for Active; values are 0..1 floats
    if kind.lower().startswith("pend"):
        # #B00020 approx
        return {"red": 0.69, "green": 0.0, "blue": 0.125}
    # #6A0DAD approx (royal purple)
    return {"red": 0.415, "green": 0.051, "blue": 0.678}


def _build_tab_requests(company_id: str, kind: str, rows: List[List[Any]]) -> Tuple[int, List[Dict[str, Any]]]:
    """Build requests to add/format/clear/write a single tab.

    Returns (sheet_id, requests).
    """
    # Standardize to "{CID} {Kind}" (e.g., "710 Active")
    title = f"{company_id} {kind}"
    sheet_id = _deterministic_sheet_id(company_id, kind)

    # Compute a reasonable column count
    column_count = max((len(r) for r in rows), default=1)
    row_count = max(len(rows), 1) + 50

    requests: List[Dict[str, Any]] = []

    # Ensure tab exists (idempotent only if this tool created it previously with same sheetId)
    requests.append(
        {
            "addSheet": {
                "properties": {
                    "sheetId": sheet_id,
                    "title": title,
                    "gridProperties": {
                        "frozenRowCount": 1,
                        "rowCount": row_count,
                        "columnCount": max(column_count, 1),
                    },
                }
            }
        }
    )

    # Global dark theme for this tab
    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0},
                        "textFormat": {"foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}},
                        "wrapStrategy": "WRAP",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat.foregroundColor,wrapStrategy)",
            }
        }
    )

    # Header styling (row 1)
    requests.append(
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": _accent_color(kind),
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat.bold,horizontalAlignment)",
            }
        }
    )

    # Clear all values, then write fresh values starting at A1
    requests.append(
        {
            "updateCells": {
                "range": {"sheetId": sheet_id},
                "fields": "userEnteredValue",
            }
        }
    )

    if rows:
        requests.append(
            {
                "updateCells": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 0, "startColumnIndex": 0},
                    "fields": "userEnteredValue",
                    "rows": [_to_row(r) for r in rows],
                }
            }
        )

    return sheet_id, requests


def _get_service():
    """Build Sheets service using GOOGLE_SERVICE_ACCOUNT path or default local path.

    If KYLO_SHEETS_DRY_RUN is true, returns None (caller should not execute).
    """
    dry_run = os.environ.get("KYLO_SHEETS_DRY_RUN", "false").lower() in ("1", "true", "yes", "y")
    if dry_run:
        return None

    if Credentials is None or build is None:
        raise RuntimeError("google-api-python-client not available; set KYLO_SHEETS_DRY_RUN=true for dry runs.")

    # Prefer GOOGLE_APPLICATION_CREDENTIALS; else YAML; else GOOGLE_SERVICE_ACCOUNT; else default
    sa_ref = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not sa_ref:
        try:
            cfg = load_config()
            sa_ref = cfg.get("google.service_account_json_path")
        except Exception:
            sa_ref = None
    if not sa_ref:
        sa_ref = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    if not sa_ref:
        # Default to local secrets path relative to repo root
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        sa_ref = os.path.join(repo_root, "secrets", "service_account.json")

    # Accept either a file path or inline JSON creds
    if sa_ref.strip().startswith("{"):
        # Treat as JSON string
        import json
        info = json.loads(sa_ref)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    elif sa_ref.strip().lower().startswith("gcp://"):
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT refers to a Secret Manager alias (gcp://...). "
            "Resolve it to JSON and set GOOGLE_SERVICE_ACCOUNT to the JSON or to a temp file path."
        )
    else:
        creds = Credentials.from_service_account_file(sa_ref, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def write_projection(
    spreadsheet_id: str,
    company_tabs: Mapping[str, Mapping[str, List[List[Any]]]],
) -> Dict[str, Any]:
    """Mirror per-company Pending/Active tables to a spreadsheet in one batchUpdate.

    - Ensures each company's tabs exist (deterministic ids) via addSheet
    - Clears prior values
    - Bulk writes provided values
    - Applies dark theme (black bg, white text) and header accent (red/purple)

    Environment:
      - GOOGLE_SERVICE_ACCOUNT: path to service account json (optional; default secrets/service_account.json)
      - KYLO_SHEETS_DRY_RUN: if true, do not call the API; return payload
    """

    trace_id = start_trace(kind="poster", company_id="*multi*")
    requests: List[Dict[str, Any]] = []

    # For each company, build tabs for Pending and Active
    for company_id, tables in company_tabs.items():
        pending_rows = tables.get("Pending") or []
        active_rows = tables.get("Active") or []

        _, reqs_p = _build_tab_requests(company_id, "Pending", pending_rows)
        _, reqs_a = _build_tab_requests(company_id, "Active", active_rows)
        requests.extend(reqs_p)
        requests.extend(reqs_a)

    # Single batchUpdate payload
    body = {"requests": requests}
    # when your code has finished building the `requests` list for batchUpdate:
    emit("poster", trace_id, "batch_update_built", {
        "tabs": list(company_tabs.keys()),
        "ops_count": len(requests),
    })

    service = _get_service()
    if service is None:
        # Dry run: return the payload for inspection/testing
        return {"dry_run": True, "spreadsheetId": spreadsheet_id, "body": body}

    # Execute exactly one batchUpdate call
    resp = (
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
        .execute()
    )
    # right after executing service.spreadsheets().batchUpdate(...).execute()
    emit("poster", trace_id, "batch_update_sent", {
        "tabs_written": list(company_tabs.keys()),
        "status": "ok"
    })
    return resp


__all__ = ["write_projection"]


