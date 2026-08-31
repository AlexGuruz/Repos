"""Unit tests for forward liquidity projection (continuous actual->projected EOD)."""

from __future__ import annotations

from datetime import date

from services.posting.projection_forecast import (
    BANK_NET_TARGETS,
    CASH_NET_TARGETS,
    net_sumif_formula,
    project_forward_eod,
)


def test_pool_maps_use_income_net_not_transfer_cols():
    cash = dict(CASH_NET_TARGETS)
    bank = dict(BANK_NET_TARGETS)
    # INCOME cash/bank NET columns at zone ends, never the transfer nets (AA/AB).
    assert cash["INCOME"] == "M"
    assert bank["INCOME"] == "W"
    assert "AA" not in cash.values() and "AB" not in cash.values()
    assert "AA" not in bank.values() and "AB" not in bank.values()
    # Twin expense tabs land in the correct pool (day net col B).
    assert cash["CASH EXPENSES"] == "B"
    assert bank["BANK EXPENSES"] == "B"
    # Zone helper nets (left=cash / right=bank layout).
    assert cash["PAYROLL"] == "T" and bank["PAYROLL"] == "W"
    assert cash["JGD"] == "F" and bank["JGD"] == "K"


def test_net_sumif_formula_quotes_tabs_with_spaces():
    f = net_sumif_formula([("CASH EXPENSES", "B"), ("INCOME", "M")], "$B23")
    assert f.startswith("=")
    # Spine-only ranges (row 20+) so month rollups in rows 2–13 never match.
    assert "SUMIF('CASH EXPENSES'!$A$20:$A,$B23,'CASH EXPENSES'!$B$20:$B)" in f
    assert "SUMIF(INCOME!$A$20:$A,$B23,INCOME!$M$20:$M)" in f
    assert "IFERROR(" in f


def test_forward_eod_continuity_at_boundary():
    dates = [date(2026, 7, 16), date(2026, 7, 17)]
    cash_net = {date(2026, 7, 16): -100.0, date(2026, 7, 17): -50.0}
    bank_net = {date(2026, 7, 16): 200.0, date(2026, 7, 17): 0.0}
    res = project_forward_eod(
        boundary_bank=1000.0,
        boundary_cash=500.0,
        dates=dates,
        cash_net=cash_net,
        bank_net=bank_net,
        in_transit={date(2026, 7, 16): 25.0},
    )
    # Day 1 continues from boundary.
    assert res.bank[0] == 1200.0
    assert res.cash[0] == 400.0
    assert res.in_transit[0] == 25.0
    assert res.available[0] == 1625.0
    # Day 2 accumulates, K carries.
    assert res.bank[1] == 1200.0
    assert res.cash[1] == 350.0
    assert res.in_transit[1] == 25.0
    assert res.available[1] == 1575.0


def test_projected_shortfall_drives_available_negative():
    # Big projected expenses beyond any projected income -> Available goes negative.
    dates = [date(2026, 8, d) for d in (1, 2, 3)]
    cash_net = {dates[0]: -2000.0, dates[1]: -2000.0, dates[2]: -2000.0}
    bank_net = {d: 0.0 for d in dates}
    res = project_forward_eod(
        boundary_bank=1000.0,
        boundary_cash=1500.0,
        dates=dates,
        cash_net=cash_net,
        bank_net=bank_net,
    )
    assert res.available[0] == 500.0   # 1000 + (1500-2000)
    assert res.available[1] == -1500.0
    assert res.available[2] == -3500.0
    assert res.cash[-1] == -4500.0
