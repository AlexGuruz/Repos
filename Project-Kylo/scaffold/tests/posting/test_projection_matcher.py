"""Unit tests for projection matcher (drift consume, ambiguity, partial)."""

from __future__ import annotations

from services.posting.projection_matcher import (
    ActualCell,
    ProjectionCandidate,
    find_projection_matches,
    projection_match_config,
)


def _actual(tab, header, date_key, amount, a1=""):
    return ActualCell(
        tab=tab,
        header=header,
        date_key=date_key,
        amount=amount,
        txn_uids={"uid-1"},
        a1=a1 or f"'{tab}'!C20",
    )


def _proj(tab, header, date_key, amount, a1=""):
    return ProjectionCandidate(
        tab=tab,
        header=header,
        date_key=date_key,
        amount=amount,
        a1=a1 or f"'{tab}'!C21",
    )


def test_drift_consume_clears_projection():
    """Actual on D, projection on D+1 same header/amount → consume."""
    actual = _actual("BANK EXPENSES", "OEC", "7/16/26", -327.91)
    proj = _proj("BANK EXPENSES", "OEC", "7/17/26", -327.91, "'BANK EXPENSES'!G50")
    result = find_projection_matches([actual], [proj], window_days=2, amount_tolerance=0.02)
    assert len(result.consumed) == 1
    assert result.consumed[0].match_type == "drift_consume"
    assert result.cleared_a1s == ["'BANK EXPENSES'!G50"]


def test_ambiguous_two_equal_candidates():
    actual = _actual("BANK EXPENSES", "AT&T", "7/17/26", -366.04)
    p1 = _proj("BANK EXPENSES", "AT&T", "7/16/26", -366.04, "'BANK EXPENSES'!H10")
    p2 = _proj("BANK EXPENSES", "AT&T", "7/18/26", -366.04, "'BANK EXPENSES'!H12")
    result = find_projection_matches([actual], [p1, p2], window_days=2, amount_tolerance=0.02)
    assert len(result.consumed) == 0
    assert len(result.review_queue) >= 2
    assert any(m.match_type == "ambiguous" for m in result.review_queue)


def test_partial_amount_not_consumed():
    actual = _actual("NUGZ COG", "ESTIMATED TAX", "7/19/26", -3000.0)
    proj = _proj("NUGZ COG", "ESTIMATED TAX", "7/20/26", -2990.0, "'NUGZ COG'!F30")
    result = find_projection_matches([actual], [proj], window_days=2, amount_tolerance=0.02)
    assert len(result.consumed) == 0
    assert any(m.match_type == "partial" for m in result.review_queue)


def test_same_day_not_matched_as_drift():
    """Same date is poster overwrite; matcher skips same-day pairs."""
    actual = _actual("INCOME", "REG 1", "7/15/26", 500.0)
    proj = _proj("INCOME", "REG 1", "7/15/26", 500.0, "'INCOME'!C20")
    result = find_projection_matches([actual], [proj], window_days=2, amount_tolerance=0.02)
    assert len(result.consumed) == 0


def test_sign_mismatch_rejected():
    actual = _actual("BANK EXPENSES", "OEC", "7/16/26", -327.91)
    proj = _proj("BANK EXPENSES", "OEC", "7/17/26", 327.91)
    result = find_projection_matches([actual], [proj], window_days=2, amount_tolerance=0.02)
    assert len(result.consumed) == 0


def test_projection_match_config_defaults():
    cfg = {
        "posting": {
            "projection_match": {
                "enabled": True,
                "window_days": 2,
                "amount_tolerance": 0.02,
            }
        }
    }
    pm = projection_match_config(cfg)
    assert pm["enabled"] is True
    assert pm["window_days"] == 2
    assert pm["amount_tolerance"] == 0.02
    assert pm["clear_on_match"] is True
