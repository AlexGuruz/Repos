from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import os
import random

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _to_cell(value: Any) -> Dict[str, Any]:
    return {"userEnteredValue": {"stringValue": "" if value is None else str(value)}}


def _to_row(values: List[Any]) -> Dict[str, Any]:
    return {"values": [_to_cell(v) for v in values]}


def _generate_unique_sheet_id(existing_ids: List[int]) -> int:
    existing = set(existing_ids)
    # Use a high range to avoid collisions with common human-added sheets
    for _ in range(1000):
        candidate = random.randint(1_000_000, 2_147_000_000)
        if candidate not in existing:
            return candidate
    # Fallback: deterministic offset
    return max(existing or [0]) + 1


def _get_service(service_account_path: str):
    creds = Credentials.from_service_account_file(service_account_path, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


@dataclass
class SheetResolution:
    pending_id: int
    active_id: int
    existing_titles_to_ids: Dict[str, int]
    existing_protection_descriptions_by_sheet_id: Dict[int, List[str]]


def resolve_sheet_ids(
    service, spreadsheet_id: str, pending_title: str, active_title: str
) -> SheetResolution:
    # Request metadata for sheets and protected ranges; omit overly specific
    # field selection to avoid mismatch with API (sheetId is nested under range).
    meta = (
        service.spreadsheets()
        .get(
            spreadsheetId=spreadsheet_id,
            # fields="sheets(properties(sheetId,title),protectedRanges(description,range))",
        )
        .execute()
    )

    titles_to_ids: Dict[str, int] = {}
    protections_by_sheet: Dict[int, List[str]] = {}
    existing_ids: List[int] = []

    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        sid = int(props.get("sheetId"))
        title = props.get("title")
        titles_to_ids[title] = sid
        existing_ids.append(sid)

        protos = sheet.get("protectedRanges", [])
        if protos:
            protections_by_sheet[sid] = [p.get("description", "") for p in protos if p]
        else:
            protections_by_sheet[sid] = []

    pending_id = titles_to_ids.get(pending_title)
    active_id = titles_to_ids.get(active_title)

    # Caller may choose to generate explicit ids for missing sheets
    if pending_id is None:
        pending_id = _generate_unique_sheet_id(existing_ids)
    if active_id is None:
        active_id = _generate_unique_sheet_id(existing_ids + [pending_id])

    return SheetResolution(
        pending_id=pending_id,
        active_id=active_id,
        existing_titles_to_ids=titles_to_ids,
        existing_protection_descriptions_by_sheet_id=protections_by_sheet,
    )


def build_setup_requests(company_id: str, pending_sheet_id: int, active_sheet_id: int, add_missing: Tuple[bool, bool]) -> List[Dict[str, Any]]:
    # Use the new tab naming convention
    pending_title = f"{company_id} Pending"
    active_title = f"{company_id} Active"

    requests: List[Dict[str, Any]] = []

    add_pending, add_active = add_missing
    if add_pending:
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": pending_sheet_id,
                        "title": pending_title,
                        "gridProperties": {
                            "frozenRowCount": 1,
                            "rowCount": 2000,
                            "columnCount": 11,
                        },
                    }
                }
            }
        )
    if add_active:
        requests.append(
            {
                "addSheet": {
                    "properties": {
                        "sheetId": active_sheet_id,
                        "title": active_title,
                        "gridProperties": {
                            "frozenRowCount": 1,
                            "rowCount": 2000,
                            "columnCount": 12,
                        },
                    }
                }
            }
        )

    # Ensure frozen row on existing sheets as well
    requests.extend(
        [
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": pending_sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": active_sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }
            },
        ]
    )

    # Headers - Pending
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": pending_sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 11,
                },
                "fields": "userEnteredValue",
                "rows": [
                    _to_row(
                        [
                            "Row_Hash",
                            "Date",
                            "Source",
                            "Company_ID",
                            "Amount",
                            "Target_Sheet",
                            "Target_Header",
                            "Match_Notes",
                            "Approved",
                            "Rule_ID",
                            "Processed_At",
                        ]
                    )
                ],
            }
        }
    )

    # Headers - Active
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": active_sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 8,
                },
                "fields": "userEnteredValue",
                "rows": [
                    _to_row(
                        [
                            "Ruleset_Version",
                            "Effective_At",
                            "Company_ID",
                            "Source",
                            "Target_Sheet",
                            "Target_Header",
                            "Match_Notes",
                            "Created_At",
                        ]
                    )
                ],
            }
        }
    )

    # Header styling (bold, dark background, white text)
    requests.extend(
        [
            {
                "repeatCell": {
                    "range": {"sheetId": pending_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": active_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor)",
                }
            },
        ]
    )

    # Body dark theme (black background, white text)
    requests.extend(
        [
            {
                "repeatCell": {
                    "range": {"sheetId": pending_sheet_id, "startRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat.foregroundColor,backgroundColor)",
                }
            },
            {
                "repeatCell": {
                    "range": {"sheetId": active_sheet_id, "startRowIndex": 1},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                            "backgroundColor": {"red": 0, "green": 0, "blue": 0},
                        }
                    },
                    "fields": "userEnteredFormat(textFormat.foregroundColor,backgroundColor)",
                }
            },
        ]
    )

    # Tab colors (purple accent)
    tab_color = {"red": 0.4, "green": 0.0, "blue": 0.6}
    requests.extend(
        [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": pending_sheet_id, "tabColor": tab_color},
                    "fields": "tabColor",
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": active_sheet_id, "tabColor": tab_color},
                    "fields": "tabColor",
                }
            },
        ]
    )

    # Data validation - Pending Approved TRUE/FALSE (column I; index 8)
    requests.append(
        {
            "setDataValidation": {
                "range": {
                    "sheetId": pending_sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 8,
                    "endColumnIndex": 9,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [
                            {"userEnteredValue": "TRUE"},
                            {"userEnteredValue": "FALSE"},
                        ],
                    },
                    "strict": True,
                    "inputMessage": "Select TRUE to approve, FALSE to hold",
                },
            }
        }
    )

    # Data validation - Pending Company_ID fixed (column D; index 3)
    requests.append(
        {
            "setDataValidation": {
                "range": {
                    "sheetId": pending_sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 3,
                    "endColumnIndex": 4,
                },
                "rule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": company_id}],
                    },
                    "strict": True,
                    "inputMessage": f"Company_ID must be {company_id}",
                },
            }
        }
    )

    # Protections - added by caller after checking existing protections
    # System columns on Pending: Row_Hash (A; index 0) and Processed_At (K; index 10)
    # Protect Column A
    requests.append(
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": pending_sheet_id,
                        "startRowIndex": 0,
                        "startColumnIndex": 0,
                        "endColumnIndex": 1,
                    },
                    "warningOnly": False,
                    "description": "System-managed column (Row_Hash)",
                }
            }
        }
    )
    # Protect Column K
    requests.append(
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {
                        "sheetId": pending_sheet_id,
                        "startRowIndex": 0,
                        "startColumnIndex": 10,
                        "endColumnIndex": 11,
                    },
                    "warningOnly": False,
                    "description": "System-managed column (Processed_At)",
                }
            }
        }
    )

    # Protection - entire Active tab
    requests.append(
        {
            "addProtectedRange": {
                "protectedRange": {
                    "range": {"sheetId": active_sheet_id},
                    "warningOnly": False,
                    "description": "Active rules are system-projected",
                }
            }
        }
    )

    return requests


def ensure_setup_batch(
    service,
    spreadsheet_id: str,
    company_id: str,
    assign_explicit_ids: bool = True,
    execute: bool = False,
) -> Dict[str, Any]:
    """
    Preflight metadata, add missing tabs, and apply headers/validation/protections in one batch.

    Returns the API response if execute=True, else the batchUpdate payload dict.
    """
    # Use the new tab naming convention
    pending_title = f"{company_id} Pending"
    active_title = f"{company_id} Active"

    res = resolve_sheet_ids(service, spreadsheet_id, pending_title, active_title)

    pending_exists = pending_title in res.existing_titles_to_ids
    active_exists = active_title in res.existing_titles_to_ids

    # If a sheet already exists, we must use its actual id (resolved above)
    pending_id = res.existing_titles_to_ids.get(pending_title, res.pending_id)
    active_id = res.existing_titles_to_ids.get(active_title, res.active_id)

    requests = build_setup_requests(
        company_id=company_id,
        pending_sheet_id=pending_id,
        active_sheet_id=active_id,
        add_missing=(not pending_exists, not active_exists),
    )

    # Avoid duplicate protections if a description already exists on that sheet
    # (filter out duplicates by description match)
    def _filter_protection(req: Dict[str, Any]) -> bool:
        if "addProtectedRange" not in req:
            return True
        pr = req["addProtectedRange"]["protectedRange"]
        desc = pr.get("description", "")
        rng = pr.get("range", {})
        sid = rng.get("sheetId")
        existing = res.existing_protection_descriptions_by_sheet_id.get(int(sid or -1), [])
        return desc not in existing

    filtered_requests = [r for r in requests if _filter_protection(r)]

    payload = {"requests": filtered_requests}

    if execute:
        return (
            service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=payload)
            .execute()
        )
    return payload


def build_per_run_requests(
    active_sheet_id: int,
    pending_sheet_id: int,
    active_rows: List[List[Any]],
    pending_writebacks: List[Tuple[int, List[Tuple[Any, Any]]]],
) -> List[Dict[str, Any]]:
    """
    Build per-run batch requests:
      1) Clear Active body
      2) Write Active rows (values in active_rows, starting row 2)
      3) Write Processed_At + Row_Hash to Pending for promoted rows

    pending_writebacks: list of tuples of (start_row_index, rows_values)
      where rows_values is a list of (processed_at, row_hash).
    """
    requests: List[Dict[str, Any]] = []

    # Clear Active (values only) from row 2 onward
    requests.append(
        {
            "updateCells": {
                "range": {"sheetId": active_sheet_id, "startRowIndex": 1},
                "fields": "userEnteredValue",
            }
        }
    )

    # Write Active rows
    requests.append(
        {
            "updateCells": {
                "range": {
                    "sheetId": active_sheet_id,
                    "startRowIndex": 1,
                    "startColumnIndex": 0,
                },
                "fields": "userEnteredValue",
                "rows": [_to_row(row) for row in active_rows],
            }
        }
    )

    # Pending writebacks in contiguous blocks for columns J (9) and K (10)
    for start_row_index, rows in pending_writebacks:
        requests.append(
            {
                "updateCells": {
                    "range": {
                        "sheetId": pending_sheet_id,
                        "startRowIndex": start_row_index,
                        "endRowIndex": start_row_index + len(rows),
                        "startColumnIndex": 9,
                        "endColumnIndex": 11,
                    },
                    "fields": "userEnteredValue",
                    "rows": [_to_row([p, h]) for (p, h) in rows],
                }
            }
        )

    return requests


def build_per_run_payload(
    active_sheet_id: int,
    pending_sheet_id: int,
    active_rows: List[List[Any]],
    pending_writebacks: List[Tuple[int, List[Tuple[Any, Any]]]],
) -> Dict[str, Any]:
    return {"requests": build_per_run_requests(active_sheet_id, pending_sheet_id, active_rows, pending_writebacks)}


def example_usage():
    """Small example showing how to assemble and optionally execute the setup batch.

    Environment variables:
      - SPREADSHEET_ID
      - COMPANY_ID
      - SA_PATH (optional; defaults to secrets/service_account.json)
      - EXECUTE (optional; "1" to execute, else just prints the payload)
    """
    spreadsheet_id = os.environ["SPREADSHEET_ID"]
    company_id = os.environ["COMPANY_ID"]
    sa_path = os.environ.get("SA_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "secrets", "service_account.json"))
    execute = os.environ.get("EXECUTE") == "1"

    service = _get_service(sa_path)
    payload_or_response = ensure_setup_batch(service, spreadsheet_id, company_id, execute=execute)
    print(payload_or_response)


if __name__ == "__main__":
    example_usage()


