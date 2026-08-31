"""Unit tests for In-Transit drift detection + email formatting."""

from __future__ import annotations

from datetime import date

from services.posting.transfer_matcher import TransferLeg
from services.posting.in_transit_drift import (
    DEFAULT_DRIFT_DAYS,
    drift_dedupe_key,
    drift_totals_by_pool,
    expected_pool_for,
    find_drifting_transfers,
    format_drift_email,
)


def _leg(side, family, d, amount, uid, desc=""):
    return TransferLeg(side, family, d, amount, uid, desc)


def test_to_bank_cash_out_drifts_to_bank():
    legs = [_leg("cash_out", "to_bank", date(2026, 7, 1), 1000.0, "c1", "TO BANK")]
    drifts = find_drifting_transfers(legs, date(2026, 7, 15), drift_days=7)
    assert len(drifts) == 1
    d = drifts[0]
    assert d.expected_pool == "BANK"
    assert d.kind == "in_transit"
    assert d.age_days == 14
    assert d.amount == 1000.0


def test_withdraw_bank_out_drifts_to_cash():
    legs = [_leg("bank_out", "from_bank", date(2026, 7, 1), 500.0, "b1", "WITHDRAW")]
    drifts = find_drifting_transfers(legs, date(2026, 7, 15), drift_days=7)
    assert len(drifts) == 1
    assert drifts[0].expected_pool == "CASH"


def test_within_window_not_flagged():
    legs = [_leg("cash_out", "to_bank", date(2026, 7, 12), 300.0, "c1")]
    drifts = find_drifting_transfers(legs, date(2026, 7, 15), drift_days=7)
    assert drifts == []


def test_exactly_threshold_not_flagged():
    # age == drift_days is not yet "over" the threshold.
    legs = [_leg("cash_out", "to_bank", date(2026, 7, 8), 300.0, "c1")]
    drifts = find_drifting_transfers(legs, date(2026, 7, 15), drift_days=7)
    assert drifts == []


def test_arrival_gap_excluded_by_default_included_on_flag():
    legs = [_leg("bank_in", "to_bank", date(2026, 7, 1), 900.0, "b1", "DEPOSIT")]
    assert find_drifting_transfers(legs, date(2026, 7, 15)) == []
    inc = find_drifting_transfers(legs, date(2026, 7, 15), include_arrival_gaps=True)
    assert len(inc) == 1
    assert inc[0].kind == "arrival_gap"
    assert inc[0].expected_pool == "BANK"


def test_atm_family_ignored():
    legs = [_leg("atm_out", "atm", date(2026, 6, 1), 2000.0, "a1", "ATM LOAD")]
    assert find_drifting_transfers(legs, date(2026, 7, 15)) == []


def test_totals_by_pool_and_sorting():
    legs = [
        _leg("cash_out", "to_bank", date(2026, 7, 1), 1000.0, "c1"),
        _leg("bank_out", "from_bank", date(2026, 7, 5), 250.0, "b1"),
        _leg("cash_out", "to_bank", date(2026, 6, 20), 400.0, "c2"),
    ]
    drifts = find_drifting_transfers(legs, date(2026, 7, 20), drift_days=7)
    assert len(drifts) == 3
    # oldest first
    assert drifts[0].since_date == date(2026, 6, 20)
    totals = drift_totals_by_pool(drifts)
    assert totals["BANK"] == 1400.0
    assert totals["CASH"] == 250.0


def test_format_drift_email_contains_amount_and_pool():
    legs = [_leg("cash_out", "to_bank", date(2026, 7, 1), 1000.0, "c1", "TO BANK")]
    drifts = find_drifting_transfers(legs, date(2026, 7, 15), drift_days=7)
    subject, body = format_drift_email(drifts, date(2026, 7, 15), drift_days=7)
    assert "1,000.00" in subject
    assert "BANK" in body
    assert "1,000.00" in body


def test_dedupe_key_stable():
    leg = _leg("cash_out", "to_bank", date(2026, 7, 1), 1000.0, "uid-42")
    drifts = find_drifting_transfers([leg], date(2026, 7, 15))
    assert drift_dedupe_key(drifts[0]) == "uid-42"


def test_expected_pool_map():
    assert expected_pool_for("cash_out") == "BANK"
    assert expected_pool_for("bank_out") == "CASH"
    assert DEFAULT_DRIFT_DAYS == 7
