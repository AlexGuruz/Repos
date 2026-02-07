import argparse
import json
import os
import re
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def extract_spreadsheet_id(workbook: str) -> str:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", workbook)
    return match.group(1) if match else workbook


def column_index_to_letter(index_zero_based: int) -> str:
    index = index_zero_based
    letters = []
    while index >= 0:
        index, remainder = divmod(index, 26)
        letters.append(chr(ord('A') + remainder))
        index -= 1
    return ''.join(reversed(letters))


def infer_columns_from_headers(headers: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not headers:
        return mapping

    # Heuristics (case-insensitive exact token match)
    normalized = [h.strip().lower() if isinstance(h, str) else "" for h in headers]
    wanted: List[Tuple[str, List[str]]] = [
        ("Date", ["date"]),
        ("Amount", ["amount", "$", "total"]),
    ]
    for label, keys in wanted:
        for i, h in enumerate(normalized):
            if h in keys:
                mapping[label] = column_index_to_letter(i)
                break
    return mapping


def load_sheets_service(creds_path: str):
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def snapshot_workbook(workbook: str, output_path: str, header_row: int = 19) -> Dict:
    load_dotenv()
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.exists(creds_path):
        raise SystemExit("GOOGLE_APPLICATION_CREDENTIALS not set or file not found")

    service = load_sheets_service(creds_path)
    spreadsheet_id = extract_spreadsheet_id(workbook)

    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])

    layout = {"sheets": {}}
    for sh in sheets:
        title = sh["properties"]["title"]
        # Read header row 19 (1-based indexing in A1 notation)
        rng = f"{title}!A{header_row}:ZZ{header_row}"
        values_resp = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=rng)
            .execute()
        )
        row = values_resp.get("values", [[]])
        headers = row[0] if row else []
        columns = infer_columns_from_headers(headers)

        layout["sheets"][title] = {
            "header_rows": header_row,
            "columns": columns,
        }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=2)

    return layout


def main():
    parser = argparse.ArgumentParser(description="Snapshot workbook layout")
    parser.add_argument("--workbook", required=True, help="Workbook URL or ID")
    parser.add_argument("--out", required=True, help="Output layout JSON path")
    parser.add_argument("--header-row", type=int, default=19, help="Header row number (default 19)")
    args = parser.parse_args()

    layout = snapshot_workbook(args.workbook, args.out, header_row=args.header_row)
    print(json.dumps({"wrote": args.out, "sheets": list(layout.get("sheets", {}).keys())}))


if __name__ == "__main__":
    main()


