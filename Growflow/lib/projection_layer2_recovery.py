"""
Second-layer projection: recovery / velocity metrics per brand × category cell.

Units convention: Growflow order lines do not expose line quantity in our schema;
each counted line = 1 unit (see all_categories_inventory_and_daily_rebuild.py).

**Truth bounds:** Category/brand come from order lines and local bucket rules, not from validated
``findProducts`` / ``findProductCategories`` / ``findBrands``. Do not treat outputs as pack-level or
transfer-adjusted inventory truth until those APIs are confirmed (``docs/GROWFLOW_PLANNER_DATA_MAPPING.md``).
"""
from __future__ import annotations

import math
from typing import Any


def usable_cog_cents(gross_cents: int, cog_raw: Any) -> int:
    """COG cents if valid on line, else 0."""
    try:
        cog_i = int(cog_raw) if cog_raw is not None else None
    except (TypeError, ValueError):
        return 0
    if cog_i is None or cog_i < 0 or cog_i > gross_cents:
        return 0
    return cog_i


def months_in_window_span(span_inclusive_days: int) -> float:
    """Calendar months equivalent for annualization (365.25-day year)."""
    if span_inclusive_days <= 0:
        return 0.0
    return span_inclusive_days * 12.0 / 365.25


def avg_monthly_units_sold(units: int, span_inclusive_days: int) -> float | None:
    if units < 0 or span_inclusive_days <= 0:
        return None
    mwin = months_in_window_span(span_inclusive_days)
    if mwin <= 0:
        return None
    return units / mwin


def recovery_bucket(months: float | None) -> str | None:
    if months is None or (isinstance(months, float) and math.isnan(months)):
        return None
    if months < 0:
        return None
    if months < 0.5:  # ~2 weeks
        return "Fast (<2wk)"
    if months <= 2.0:
        return "Medium (1–2mo)"
    if months <= 3.0:
        return "Moderate (2–3mo)"
    return "Slow (>3mo)"


def layer2_row(
    *,
    allocated_cog_usd: float,
    units_sold: int,
    gross_cents: int,
    cog_cents: int,
    span_inclusive_days: int,
) -> dict[str, Any]:
    """
    Compute second-layer fields for one brand × category cell.
    Uses same span for gross/COG/units as the allocation window.

    TODO(schema truth): ``units_sold`` is order-line count; replace with real qty / package linkage when API validates
    (docs/GROWFLOW_PLANNER_DATA_MAPPING.md).
    """
    gross_usd = gross_cents / 100.0
    cog_usd = cog_cents / 100.0

    row: dict[str, Any] = {
        "trailing_units_sold": units_sold,
        "trailing_gross_usd": gross_usd,
        "trailing_cog_usd": cog_usd,
        "avg_units_per_month": None,
        "avg_cog_per_unit": None,
        "avg_retail_per_unit": None,
        "units_from_allocation": None,
        "months_to_recover_cog": None,
        "projected_revenue_from_allocated_units_usd": None,
        "projected_gross_profit_usd": None,
        "turns_per_year": None,
        "recovery_bucket": None,
        "allocation_efficiency": None,
    }

    if units_sold <= 0:
        row["recovery_bucket"] = None
        return row

    row["avg_units_per_month"] = avg_monthly_units_sold(units_sold, span_inclusive_days)
    row["avg_retail_per_unit"] = gross_usd / units_sold
    row["avg_cog_per_unit"] = cog_usd / units_sold if cog_usd > 0 else None

    if row["avg_cog_per_unit"] is None or row["avg_cog_per_unit"] <= 0:
        return row

    row["units_from_allocation"] = allocated_cog_usd / row["avg_cog_per_unit"]

    aum = row["avg_units_per_month"]
    if aum is not None and aum > 0:
        row["months_to_recover_cog"] = row["units_from_allocation"] / aum
        m = row["months_to_recover_cog"]
        if m is not None and m > 0:
            row["turns_per_year"] = 12.0 / m
        row["recovery_bucket"] = recovery_bucket(row["months_to_recover_cog"])

    ufa = row["units_from_allocation"]
    arpu = row["avg_retail_per_unit"]
    if ufa is not None and arpu is not None:
        row["projected_revenue_from_allocated_units_usd"] = ufa * arpu
        row["projected_gross_profit_usd"] = (
            row["projected_revenue_from_allocated_units_usd"] - allocated_cog_usd
        )
    if allocated_cog_usd > 0 and row["projected_revenue_from_allocated_units_usd"] is not None:
        row["allocation_efficiency"] = row["projected_revenue_from_allocated_units_usd"] / allocated_cog_usd

    return row


def cash_cycle_status_from_recovery_days(days: float | None, *, target_days: float = 14.0) -> str | None:
    """Cash discipline: implied COG recovery time at recent daily unit velocity."""
    if days is None or (isinstance(days, float) and (math.isnan(days) or math.isinf(days))):
        return None
    td = max(float(target_days), 1e-9)
    if days <= td:
        return "SAFE"
    if days <= td * 1.5:
        return "WARNING"
    return "CAPITAL RISK"


def cover_status_from_days_of_cover(days: float | None) -> str | None:
    """Demand / stocking lens (same numeric basis as cash recovery days for this model)."""
    if days is None or (isinstance(days, float) and (math.isnan(days) or math.isinf(days))):
        return None
    if days < 7.0:
        return "URGENT"
    if days < 14.0:
        return "THIN"
    if days <= 21.0:
        return "HEALTHY"
    return "HEAVY"


def layer2_row_buy_plan(
    *,
    allocated_cog_usd: float,
    recent_units_sold: int,
    recent_gross_cents: int,
    recent_cog_cents: int,
    velocity_span_inclusive_days: int,
    avg_units_per_day_override: float | None = None,
    units_from_allocation_override: float | None = None,
    planner_score: float | None = None,
    cash_cycle_days: float = 14.0,
) -> dict[str, Any]:
    """
    Buy-plan metrics from **recent** velocity only.

    **Cash model:** ``cash_recovery_days`` (= days to sell through allocated units at recent **daily** burn)
    is compared to ``cash_cycle_days`` (default 14). The allocator caps each row so deployed COG does not
    exceed **cash_cycle_days** of demand at that burn rate.

    **Demand layer:** ``units_needed_7d`` / ``14d`` / ``21d`` and ``cover_status`` describe time windows at
    the same burn rate (not on-hand inventory).

    **Grain:** Brand × format bucket — not SKU-level.
    """
    velocity_weeks = max(float(velocity_span_inclusive_days) / 7.0, 1e-9)
    gross_usd = recent_gross_cents / 100.0
    cog_usd = recent_cog_cents / 100.0

    row: dict[str, Any] = {
        "trailing_units_sold": recent_units_sold,
        "trailing_gross_usd": gross_usd,
        "trailing_cog_usd": cog_usd,
        "velocity_window_days": velocity_span_inclusive_days,
        "avg_units_per_week": None,
        "weeks_to_sell_through": None,
        "avg_units_per_month": None,
        "avg_cog_per_unit": None,
        "avg_retail_per_unit": None,
        "units_from_allocation": None,
        "months_to_recover_cog": None,
        "projected_revenue_from_allocated_units_usd": None,
        "projected_gross_profit_usd": None,
        "turns_per_year": None,
        "recovery_bucket": None,
        "allocation_efficiency": None,
        "planner_score": planner_score,
        "avg_units_per_day": None,
        "days_of_inventory": None,
        "coverage_weeks": None,
        "units_needed_7d": None,
        "units_needed_14d": None,
        "units_needed_21d": None,
        "days_of_cover": None,
        "cover_status": None,
        "cash_recovery_days": None,
        "max_cog_allowed_usd": None,
        "capped_by_cash_cycle": None,
        "cash_cycle_status": None,
    }

    if recent_units_sold <= 0:
        row["recovery_bucket"] = None
        return row

    if avg_units_per_day_override is not None and avg_units_per_day_override > 0:
        row["avg_units_per_day"] = float(avg_units_per_day_override)
        row["avg_units_per_week"] = float(avg_units_per_day_override) * 7.0
    else:
        row["avg_units_per_week"] = recent_units_sold / velocity_weeks
    row["avg_retail_per_unit"] = gross_usd / recent_units_sold
    row["avg_cog_per_unit"] = cog_usd / recent_units_sold if cog_usd > 0 else None

    if row["avg_cog_per_unit"] is None or row["avg_cog_per_unit"] <= 0:
        return row

    # Annualize for legacy columns (52 weeks / 12 months)
    row["avg_units_per_month"] = (row["avg_units_per_week"] or 0) * (52.0 / 12.0)

    if units_from_allocation_override is not None and float(units_from_allocation_override) > 0:
        row["units_from_allocation"] = float(units_from_allocation_override)
    else:
        row["units_from_allocation"] = allocated_cog_usd / row["avg_cog_per_unit"]
    upw = row["avg_units_per_week"]
    acu = row["avg_cog_per_unit"]
    if upw is not None and upw > 0 and acu is not None:
        if row["avg_units_per_day"] is None:
            row["avg_units_per_day"] = float(upw) / 7.0
        ad = row["avg_units_per_day"]
        if ad is not None and ad > 0:
            row["units_needed_7d"] = ad * 7.0
            row["units_needed_14d"] = ad * 14.0
            row["units_needed_21d"] = ad * 21.0
            row["max_cog_allowed_usd"] = float(ad) * float(cash_cycle_days) * float(acu)
        else:
            row["max_cog_allowed_usd"] = None
    if upw is not None and upw > 0 and row["units_from_allocation"] is not None:
        ad = row["avg_units_per_day"]
        ufa_f = float(row["units_from_allocation"])
        row["coverage_weeks"] = ufa_f / float(upw)
        row["weeks_to_sell_through"] = row["coverage_weeks"]
        if ad is not None and ad > 0:
            row["days_of_inventory"] = ufa_f / ad
            row["days_of_cover"] = row["days_of_inventory"]
            row["cash_recovery_days"] = row["days_of_inventory"]
        else:
            row["days_of_inventory"] = None
            row["days_of_cover"] = None
            row["cash_recovery_days"] = None
        wst = row["weeks_to_sell_through"]
        dod = row["days_of_inventory"]
        if dod is not None:
            row["cash_cycle_status"] = cash_cycle_status_from_recovery_days(
                float(dod), target_days=float(cash_cycle_days)
            )
            row["cover_status"] = cover_status_from_days_of_cover(float(dod))
        mcap = row.get("max_cog_allowed_usd")
        if mcap is not None and float(mcap) > 0:
            row["capped_by_cash_cycle"] = bool(allocated_cog_usd + 1e-6 >= float(mcap))
        else:
            row["capped_by_cash_cycle"] = None
        row["months_to_recover_cog"] = float(wst) * (12.0 / 52.0)
        if wst and float(wst) > 0:
            row["turns_per_year"] = 52.0 / float(wst)
        row["recovery_bucket"] = recovery_bucket(row["months_to_recover_cog"])

    ufa = row["units_from_allocation"]
    arpu = row["avg_retail_per_unit"]
    if ufa is not None and arpu is not None:
        row["projected_revenue_from_allocated_units_usd"] = ufa * arpu
        row["projected_gross_profit_usd"] = (
            row["projected_revenue_from_allocated_units_usd"] - allocated_cog_usd
        )
    if allocated_cog_usd > 0 and row["projected_revenue_from_allocated_units_usd"] is not None:
        row["allocation_efficiency"] = (
            row["projected_revenue_from_allocated_units_usd"] / allocated_cog_usd
        )

    return row


def fmt_money(x: float | None) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return ""
    return f"${x:,.2f}"
