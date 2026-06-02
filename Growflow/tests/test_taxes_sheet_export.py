"""Tests for Taxes sheet export helpers."""
from __future__ import annotations

from datetime import date

from lib.daily_close_report import DailyCloseReport
from lib.taxes_sheet_export import find_tax_block_start_row, tax_values_for_report


def test_find_tax_block_start_row():
    values = [
        ["6/1/2026", "MJ / cannabis", "$137.52"],
        ["", "Sales", "$204.61"],
        ["", "Total tax", "$342.13"],
        ["6/2/2026", "MJ / cannabis", ""],
        ["", "Sales", ""],
        ["", "Total tax", ""],
    ]
    assert find_tax_block_start_row(values, date(2026, 6, 1)) == 1
    assert find_tax_block_start_row(values, date(2026, 6, 2)) == 4
    assert find_tax_block_start_row(values, date(2026, 6, 3)) is None


def test_tax_values_for_report():
    report = DailyCloseReport(
        sales_date=date(2026, 6, 1),
        timezone_label="America/Chicago",
        order_count=64,
        total_collected_cents=241489,
        subtotal_cents=257530,
        discounts_cents=16041,
        taxes_cents=34213,
        tender_cents={},
        mj_tax_cents=13752,
        sales_tax_cents=20461,
    )
    assert tax_values_for_report(report) == [["$137.52"], ["$204.61"], ["$342.13"]]
