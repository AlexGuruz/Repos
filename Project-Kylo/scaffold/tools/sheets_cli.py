from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

from .sheets_batch import _get_service, ensure_setup_batch, build_per_run_payload
from services.sheets.poster import ensure_spreadsheet, build_headers_batch


def extract_spreadsheet_id_from_url(url: str) -> Optional[str]:
    # Typical formats:
    # https://docs.google.com/spreadsheets/d/<ID>/edit#gid=0
    # https://docs.google.com/spreadsheets/d/<ID>
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    return m.group(1) if m else None


def load_companies_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_spreadsheet_id(company: Dict[str, Any], override: Optional[str]) -> str:
    if override:
        return override
    url = company.get("workbook", "")
    sid = extract_spreadsheet_id_from_url(url)
    if not sid or "<WORKBOOK_ID>" in url:
        raise ValueError("Missing or placeholder workbook URL. Provide --spreadsheet-id.")
    return sid


def cmd_setup(args: argparse.Namespace) -> None:
    cfg_path = args.config
    if not os.path.exists(cfg_path):
        print(f"Config not found: {cfg_path}", file=sys.stderr)
        sys.exit(2)

    cfg = load_companies_config(cfg_path)
    companies: List[Dict[str, Any]] = cfg.get("companies", [])
    if not companies:
        print("No companies defined in config.", file=sys.stderr)
        sys.exit(2)

    service_account_path = args.service_account or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "secrets", "service_account.json")
    service = _get_service(service_account_path)

    targets: List[Dict[str, Any]]
    if args.company_id:
        targets = [c for c in companies if c.get("company_id") == args.company_id]
        if not targets:
            print(f"Company not found: {args.company_id}", file=sys.stderr)
            sys.exit(2)
    else:
        targets = companies

    for company in targets:
        company_id = company.get("company_id")
        spreadsheet_id = resolve_spreadsheet_id(company, args.spreadsheet_id)
        print(f"Setting up tabs for company={company_id} spreadsheet={spreadsheet_id} execute={args.execute}")
        result = ensure_setup_batch(service, spreadsheet_id, company_id, execute=args.execute)
        print(result)


def cmd_per_run(args: argparse.Namespace) -> None:
    # Minimal wrapper to emit a per-run payload from provided JSON inputs.
    with open(args.active_rows_json, "r", encoding="utf-8") as f:
        active_rows = json.load(f)
    with open(args.pending_writebacks_json, "r", encoding="utf-8") as f:
        pending_writebacks = json.load(f)

    payload = build_per_run_payload(
        active_sheet_id=int(args.active_sheet_id),
        pending_sheet_id=int(args.pending_sheet_id),
        active_rows=active_rows,
        pending_writebacks=[(int(b[0]), [(r[0], r[1]) for r in b[1]]) for b in pending_writebacks],
    )
    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sheets-cli", description="Google Sheets setup and per-run helpers")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_setup = sub.add_parser("setup", help="Run one-time setup for tabs, headers, validation, protections")
    p_setup.add_argument("--config", default=os.path.join("config", "companies.json"), help="Path to companies config JSON (falls back to companies.example.json if missing)")
    p_setup.add_argument("--company-id", help="Single company_id to run; omit for all")
    p_setup.add_argument("--spreadsheet-id", help="Override spreadsheet ID (if config has placeholder)")
    p_setup.add_argument("--service-account", help="Path to service_account.json (default: secrets/service_account.json)")
    p_setup.add_argument("--execute", action="store_true", help="Actually call Sheets; otherwise just builds and prints payload after metadata preflight")
    p_setup.set_defaults(func=cmd_setup)

    p_run = sub.add_parser("per-run", help="Emit per-run batchUpdate payload from JSON inputs")
    p_run.add_argument("--active-sheet-id", required=True)
    p_run.add_argument("--pending-sheet-id", required=True)
    p_run.add_argument("--active-rows-json", required=True, help="JSON file: list[list[Any]] of Active rows")
    p_run.add_argument("--pending-writebacks-json", required=True, help="JSON file: [[startRowIndex, [[Processed_At, Row_Hash], ...]], ...]")
    p_run.set_defaults(func=cmd_per_run)

    p_apply = sub.add_parser("apply-headers", help="Ensure spreadsheet exists and apply tabs/headers/theme for companies in config")
    p_apply.add_argument("--spreadsheet-id", required=True, help="Spreadsheet title or ID or full URL")
    p_apply.add_argument("--config", default=os.path.join("config", "companies.json"))
    p_apply.add_argument("--service-account", help="Path to service_account.json (default: secrets/service_account.json)")
    p_apply.add_argument("--cids", help="Comma-separated list of company IDs to apply (overrides config)")
    p_apply.add_argument("--execute", action="store_true")
    p_apply.set_defaults(func=cmd_apply_headers)

    return p


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # If default companies.json does not exist, fall back to example
    if getattr(args, "config", None) and not os.path.exists(args.config):
        example = os.path.join("config", "companies.example.json")
        if os.path.exists(example):
            args.config = example

    args.func(args)


def cmd_apply_headers(args: argparse.Namespace) -> None:
    cfg = load_companies_config(args.config)
    companies = [c.get("company_id") for c in cfg.get("companies", []) if c.get("company_id")]
    if args.cids:
        companies = [c.strip() for c in args.cids.split(",") if c.strip()]
    if not companies:
        print("No companies found to apply", file=sys.stderr)
        sys.exit(2)

    # Ensure spreadsheet
    spreadsheet_id = ensure_spreadsheet(args.spreadsheet_id)
    payload = build_headers_batch(spreadsheet_id, companies)
    if args.execute:
        service = _get_service(args.service_account or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "secrets", "service_account.json"))
        res = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=payload).execute()
        print(f"SPREADSHEET_ID: {spreadsheet_id}")
        print(json.dumps(res))
    else:
        print(json.dumps({"spreadsheetId": spreadsheet_id, **payload}, indent=2))


if __name__ == "__main__":
    main()


