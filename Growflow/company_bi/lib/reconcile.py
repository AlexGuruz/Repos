"""
Layer 4: Reconcile GrowFlow sales vs recorded income (Transactions/Bank).
Supports POS-comparable income (register + square + cash_deposit only) and likely cause/confidence.
"""
from __future__ import annotations

from typing import Any

# Subcategories considered POS-comparable (till/card deposits), not generic "deposit" or other
POS_COMPARABLE_SUBCATEGORIES = frozenset({"register_deposit", "square", "cash_deposit"})


def _pos_comparable_from_subcategories(
    income_by_subcategory_by_month: dict[tuple[int, int], dict[str, float]],
) -> dict[tuple[int, int], float]:
    """Sum income in POS-comparable subcategories per month."""
    out: dict[tuple[int, int], float] = {}
    for ym, subs in income_by_subcategory_by_month.items():
        out[ym] = sum(
            amt for sub, amt in subs.items() if sub in POS_COMPARABLE_SUBCATEGORIES
        )
    return out


def reconcile_monthly(
    by_month_sales: dict[tuple[int, int], dict],
    income_by_month: dict[tuple[int, int], float],
    threshold_dollars: float = 500,
    income_by_subcategory_by_month: dict[tuple[int, int], dict[str, float]] | None = None,
) -> list[dict[str, Any]]:
    """
    List of {
      year, month, growflow_sales, recorded_income, pos_comparable_income,
      difference (vs recorded), difference_pos (GrowFlow - pos_comparable),
      flagged, note, likely_cause, confidence
    }.
    """
    all_months = sorted(set(list(by_month_sales.keys()) + list(income_by_month.keys())))
    pos_by_ym = _pos_comparable_from_subcategories(
        income_by_subcategory_by_month or {}
    )
    if income_by_subcategory_by_month:
        for ym in income_by_month:
            if ym not in pos_by_ym:
                pos_by_ym[ym] = 0.0

    out = []
    for ym in all_months:
        gross = (by_month_sales.get(ym) or {}).get("gross", 0) or 0
        income = income_by_month.get(ym, 0) or 0
        pos_income = pos_by_ym.get(ym, 0) or 0
        diff = abs(gross - income)
        diff_pos = gross - pos_income  # signed: positive = GrowFlow > POS deposits
        flagged = diff >= threshold_dollars
        # Also flag if POS-comparable differs from GrowFlow by >= threshold
        flagged_pos = abs(gross - pos_income) >= threshold_dollars

        note = ""
        if flagged:
            if gross > income:
                note = "Recorded income less than GrowFlow sales; possible timing (deposits next month), refunds, or fees."
            else:
                note = "Recorded income greater than GrowFlow sales; possible other income or timing."

        likely_cause = ""
        confidence = "low"
        if income_by_subcategory_by_month:
            if abs(diff_pos) < threshold_dollars:
                likely_cause = "POS-comparable aligns with GrowFlow."
                confidence = "high"
            elif diff_pos > 0:
                likely_cause = "POS deposits (reg+square+cash) less than GrowFlow; timing lag or deposits in other categories."
                confidence = "medium"
            else:
                likely_cause = "POS deposits exceed GrowFlow; possible duplicate recording or other income in POS buckets."
                confidence = "medium"

        out.append({
            "year": ym[0],
            "month": ym[1],
            "growflow_sales": round(gross, 2),
            "recorded_income": round(income, 2),
            "pos_comparable_income": round(pos_income, 2),
            "difference": round(diff, 2),
            "difference_pos": round(diff_pos, 2),
            "flagged": flagged or flagged_pos,
            "note": note,
            "likely_cause": likely_cause,
            "confidence": confidence,
        })
    return out
