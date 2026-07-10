"""
Append a two-page Trip Sheet (instructions + printable log table) to a Google Doc tab,
using the same Stashbox service account resolution as other Growflow tools.

Prerequisites:
  - Service account JSON (STASHBOX_SERVICE_ACCOUNT, etc.; see lib.stashbox_sheets_auth).
  - In Google Docs: Share the document with the service account client_email as Editor.
  - Docs API enabled for the GCP project that owns the service account.

Example:
  python scripts/build_trip_sheet_google_doc.py --dry-run   # prints resolved API tab id
  python scripts/build_trip_sheet_google_doc.py --document-id <DOC_ID> --tab-id t.0

Note: The ``?tab=`` value in the browser URL is not always the same as the Docs API ``tabId``.
Use ``--dry-run`` to list API tab ids, or ``--first-tab`` (default when --tab-id omitted).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Allow running as script from repo root or Growflow/
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _resolve_tab_id(doc: dict, tab_id: str | None) -> str:
    tabs = doc.get("tabs") or []
    if not tabs:
        raise SystemExit(
            "This document has no tabs in API shape. If it is an older single-body doc, "
            "omit --tab-id (first segment is used). For tabbed docs, pass --tab-id."
        )
    if tab_id:
        for t in tabs:
            tid = (t.get("tabProperties") or {}).get("tabId")
            if tid == tab_id:
                return tab_id
        names = [(t.get("tabProperties") or {}).get("tabId") for t in tabs]
        raise SystemExit(f"--tab-id {tab_id!r} not found. Known tab ids: {names}")
    tid = (tabs[0].get("tabProperties") or {}).get("tabId")
    if not tid:
        raise SystemExit("Could not read tabId from first tab.")
    return tid


def _find_last_table(body: dict) -> dict | None:
    for el in reversed(body.get("content") or []):
        if "table" in el:
            return el
    return None


def _cell_insert_locations(table_el: dict) -> list[list[int]]:
    """For each cell, index where insertText should place content (start of cell text)."""
    out: list[list[int]] = []
    for row in table_el["table"]["tableRows"]:
        row_ix: list[int] = []
        for cell in row["tableCells"]:
            idx = None
            for se in cell.get("content") or []:
                if "paragraph" not in se:
                    continue
                para = se["paragraph"]
                elems = para.get("elements") or []
                if elems:
                    idx = elems[0]["startIndex"]
                else:
                    idx = para.get("startIndex", 1)
                break
            if idx is None:
                idx = 1
            row_ix.append(idx)
        out.append(row_ix)
    return out


def _document_tab_body(doc: dict, tab_id: str) -> dict:
    for t in doc.get("tabs") or []:
        if (t.get("tabProperties") or {}).get("tabId") == tab_id:
            return (t.get("documentTab") or {}).get("body") or {"content": []}
    raise SystemExit(f"tab body not found for tab_id={tab_id!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Append Trip Sheet pages to a Google Doc tab.")
    parser.add_argument(
        "--document-id",
        default=os.environ.get("TRIP_SHEET_DOC_ID", "1HGFBOS_JLIL5JT_EGad9dHpHtVYYG0zBAaQoXXy8QA8"),
        help="Google Doc ID from the /document/d/<ID>/edit URL.",
    )
    parser.add_argument(
        "--tab-id",
        default=os.environ.get("TRIP_SHEET_TAB_ID"),
        help="Docs API tab id (see --dry-run). Browser ?tab= may differ; omit for first tab.",
    )
    parser.add_argument(
        "--first-tab",
        action="store_true",
        help="Resolve the first tab in the document instead of --tab-id.",
    )
    parser.add_argument(
        "--sheets-service-account",
        dest="service_account",
        default=None,
        help="Path to service account JSON (same flag name as other scripts).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print tab id and exit without writing.",
    )
    args = parser.parse_args()

    from lib.stashbox_sheets_auth import docs_service

    svc = docs_service(args.service_account)
    doc = svc.documents().get(documentId=args.document_id, includeTabsContent=True).execute()

    tab_id_arg = None if args.first_tab else ((args.tab_id or "").strip() or None)
    tab_id = _resolve_tab_id(doc, tab_id_arg)

    if args.dry_run:
        print(f"document_id={args.document_id}\ntab_id={tab_id}\ndry-run: no writes.")
        return

    page1 = (
        "TRIP SHEET — HOW TO USE (Page 1)\n\n"
        "Purpose\n"
        "This trip sheet is a lightweight compliance and operations log for inventory "
        "movement between locations (deliveries, transfers, vendor pickups). One row "
        "per trip (or per vehicle leg if you split legs).\n\n"
        "Two-page layout\n"
        "• Page 1 (this page): definitions, responsibilities, and daily workflow.\n"
        "• Page 2: a blank table you duplicate or extend as you add trips.\n\n"
        "Before you depart\n"
        "1. Fill Trip date, Driver, Vehicle, and Route / stops (addresses or store codes).\n"
        "2. Record the Manifest / transfer reference (e.g. Growflow transfer id or paper manifest #).\n"
        "3. Note seal numbers if your jurisdiction or SOP requires them.\n"
        "4. Record odometer at departure and time out.\n\n"
        "At each stop\n"
        "• Verify quantities and package labels against the manifest before the vehicle leaves.\n"
        "• If anything does not match, stop the move and document under Notes / discrepancies.\n\n"
        "After return\n"
        "• Record time in and ending odometer.\n"
        "• Driver signs; receiving manager signs on the receiving copy if you run duplicate sheets.\n"
        "• File with batch paperwork or scan into your document store per company retention policy.\n\n"
        "Tips\n"
        "• Duplicate the table block in Google Docs for more rows, or add rows inside the table "
        "(right-click in the table → Insert row below).\n"
        "• Keep one tab per facility or per month if this doc grows large.\n\n"
    )

    requests: list[dict] = [
        {
            "insertText": {
                "text": page1,
                "endOfSegmentLocation": {"segmentId": "", "tabId": tab_id},
            }
        },
        {
            "insertPageBreak": {
                "endOfSegmentLocation": {"segmentId": "", "tabId": tab_id},
            }
        },
        {
            "insertText": {
                "text": "TRIP LOG TABLE (Page 2)\n\n",
                "endOfSegmentLocation": {"segmentId": "", "tabId": tab_id},
            }
        },
        {
            "insertTable": {
                "rows": 14,
                "columns": 8,
                "endOfSegmentLocation": {"segmentId": "", "tabId": tab_id},
            }
        },
    ]

    svc.documents().batchUpdate(documentId=args.document_id, body={"requests": requests}).execute()

    doc2 = svc.documents().get(documentId=args.document_id, includeTabsContent=True).execute()
    body = _document_tab_body(doc2, tab_id)
    table_el = _find_last_table(body)
    if not table_el or "table" not in table_el:
        raise SystemExit("Could not locate inserted table in document.")

    headers = [
        "Trip date",
        "Driver",
        "Vehicle / ID",
        "Route / stops",
        "Manifest / transfer #",
        "Seals (if any)",
        "Odometer out → in",
        "Time out / in & notes",
    ]

    locs = _cell_insert_locations(table_el)
    if len(locs) < 1 or len(locs[0]) != len(headers):
        raise SystemExit(f"Unexpected table shape rows={len(locs)} cols={len(locs[0]) if locs else 0}")

    # One batch: insert right-to-left so earlier cell indices stay valid (sequential API updates).
    fill_requests: list[dict] = []
    for col in range(len(headers) - 1, -1, -1):
        fill_requests.append(
            {
                "insertText": {
                    "text": headers[col],
                    "location": {"index": locs[0][col], "tabId": tab_id},
                }
            }
        )
    svc.documents().batchUpdate(documentId=args.document_id, body={"requests": fill_requests}).execute()

    print(
        f"Appended trip sheet to document\n"
        f"  https://docs.google.com/document/d/{args.document_id}/edit#tab={tab_id}\n"
        f"tab_id={tab_id}"
    )


if __name__ == "__main__":
    main()
