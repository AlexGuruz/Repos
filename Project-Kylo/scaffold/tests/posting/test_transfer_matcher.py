"""Unit tests for transfer / in-transit matcher."""

from __future__ import annotations

from datetime import date

from services.posting.transfer_matcher import (
    TransferLeg,
    match_transfers,
    running_in_transit,
)


def test_to_bank_deposit_lag_preserves_available_via_k():
    """TO BANK day D, DEPOSIT D+1 → Available flat; K bridges."""
    legs = [
        TransferLeg("cash_out", "to_bank", date(2026, 7, 1), 1000.0, "c1"),
        TransferLeg("bank_in", "to_bank", date(2026, 7, 2), 1000.0, "b1"),
    ]
    r = match_transfers(legs, window_days=3)
    assert len(r.matches) == 1
    assert r.by_date[date(2026, 7, 1)].cash == -1000.0
    assert r.by_date[date(2026, 7, 1)].in_transit == 1000.0
    assert r.by_date[date(2026, 7, 2)].bank == 1000.0
    assert r.by_date[date(2026, 7, 2)].in_transit == -1000.0
    # Available day deltas: cash+k = 0; bank+k = 0
    d1 = r.by_date[date(2026, 7, 1)]
    d2 = r.by_date[date(2026, 7, 2)]
    assert abs(d1.cash + d1.bank + d1.in_transit) < 0.01
    assert abs(d2.cash + d2.bank + d2.in_transit) < 0.01


def test_from_bank_withdraw_same_day():
    legs = [
        TransferLeg("cash_in", "from_bank", date(2026, 7, 5), 500.0, "c1"),
        TransferLeg("bank_out", "from_bank", date(2026, 7, 5), 500.0, "b1"),
    ]
    r = match_transfers(legs)
    assert len(r.matches) == 1
    d = r.by_date[date(2026, 7, 5)]
    assert d.cash == 500.0
    assert d.bank == -500.0
    assert abs(d.in_transit) < 0.01
    assert abs(d.cash + d.bank + d.in_transit) < 0.01


def test_atm_lag_only_moves_k():
    legs = [
        TransferLeg("atm_out", "atm", date(2026, 7, 10), 2000.0, "a1"),
        TransferLeg("atm_in", "atm", date(2026, 7, 12), 2000.0, "s1"),
    ]
    r = match_transfers(legs, window_days=3)
    assert len(r.matches) == 1
    assert r.by_date[date(2026, 7, 10)].cash == 0.0
    assert r.by_date[date(2026, 7, 10)].bank == 0.0
    assert r.by_date[date(2026, 7, 10)].in_transit == 2000.0
    assert r.by_date[date(2026, 7, 12)].in_transit == -2000.0


def test_unmatched_to_bank_stays_in_transit():
    legs = [TransferLeg("cash_out", "to_bank", date(2026, 7, 15), 300.0, "c1")]
    r = match_transfers(legs)
    assert len(r.matches) == 0
    assert len(r.unmatched) == 1
    d = r.by_date[date(2026, 7, 15)]
    assert d.cash == -300.0
    assert d.in_transit == 300.0


def test_running_in_transit():
    legs = [
        TransferLeg("cash_out", "to_bank", date(2026, 1, 1), 100.0, "c1"),
        TransferLeg("bank_in", "to_bank", date(2026, 1, 3), 100.0, "b1"),
    ]
    r = match_transfers(legs, window_days=3)
    spine = [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)]
    run = running_in_transit(r.by_date, spine)
    assert run[date(2026, 1, 1)] == 100.0
    assert run[date(2026, 1, 2)] == 100.0
    assert run[date(2026, 1, 3)] == 0.0
