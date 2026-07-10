"""Write daily tax totals to the Taxes Google Sheet tab (3 rows per date)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from lib.daily_close_report import DailyCloseReport
from lib.stashbox_sheets_auth import sheets_service

DEFAULT_SPREADSHEET_ID = "1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs"
DEFAULT_SHEET_NAME = "Taxes"


def sheet_date_label(d: date) -> str:
    """Match sheet column A format (e.g. 6/1/2026)."""
    return f"{d.month}/{d.day}/{d.year}"


def _parse_sheet_date(cell: str) -> date | None:
    cell = str(cell or "").strip()
    if not cell:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cell, fmt).date()
        except ValueError:
            continue
    return None


def find_tax_block_start_row(values: list[list[Any]], sales_date: date) -> int | None:
    """
    Return 1-based sheet row of the MJ line for ``sales_date``.

    Each date block is 3 rows: MJ / cannabis, Sales, Total tax.
    """
    target = sales_date
    for idx, row in enumerate(values):
        if not row:
            continue
        parsed = _parse_sheet_date(str(row[0]))
        if parsed == target:
            return idx + 1
    return None


def format_sheet_money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def tax_values_for_report(report: DailyCloseReport) -> list[list[str]]:
    total = report.mj_tax_cents + report.sales_tax_cents
    return [
        [format_sheet_money(report.mj_tax_cents)],
        [format_sheet_money(report.sales_tax_cents)],
        [format_sheet_money(total)],
    ]


def write_taxes_to_sheet(
    report: DailyCloseReport,
    *,
    spreadsheet_id: str,
    sheet_name: str = DEFAULT_SHEET_NAME,
    service_account_path: str | None = None,
    dry_run: bool = False,
) -> str:
    """
    Update column C for the date block matching ``report.sales_date``.

    Returns the A1 range updated (e.g. 'Taxes'!C1:C3).
    """
    svc = sheets_service(service_account_path)
    read_range = f"'{sheet_name}'!A:C"
    resp = svc.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=read_range).execute()
    values = resp.get("values") or []
    start_row = find_tax_block_start_row(values, report.sales_date)
    if start_row is None:
        raise ValueError(
            f"No date row for {sheet_date_label(report.sales_date)} in '{sheet_name}' column A. "
            "Add the date cell in column A first."
        )

    end_row = start_row + 2
    update_range = f"'{sheet_name}'!C{start_row}:C{end_row}"
    body_values = tax_values_for_report(report)
    if dry_run:
        return update_range

    svc.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=update_range,
        valueInputOption="USER_ENTERED",
        body={"values": body_values},
    ).execute()
    return update_range


def resolve_taxes_sheet_config(cfg: dict[str, Any]) -> dict[str, Any]:
    gs = cfg.get("google_sheets") or {}
    ts = cfg.get("taxes_sheet") or {}
    return {
        "spreadsheet_id": ts.get("spreadsheet_id") or cfg.get("taxes_spreadsheet_id") or DEFAULT_SPREADSHEET_ID,
        "sheet_name": ts.get("sheet_name") or DEFAULT_SHEET_NAME,
        "service_account_path": (
            ts.get("service_account_path")
            or gs.get("service_account_path")
            or cfg.get("taxes_sheet_service_account_path")
        ),
    }
