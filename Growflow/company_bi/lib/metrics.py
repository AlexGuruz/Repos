"""
Layer 3: Metric engine — compute sales, expenses, overhead, labor, inventory, margins, ratios.
"""
from __future__ import annotations

from collections import defaultdict
from math import sqrt
from typing import Any

from .categorization import aggregate_by_category_month, aggregate_income_by_month


def sales_metrics(by_month_sales: dict, daily_by_month: dict) -> dict[tuple[int, int], dict]:
    """By (y,m): gross, cog, lines, trend_pct, volatility, avg_ticket_approx (gross/lines)."""
    months = sorted(by_month_sales.keys())
    result = {}
    for i, ym in enumerate(months):
        data = by_month_sales.get(ym, {})
        gross = data.get("gross", 0) or 0
        cog = data.get("cog", 0) or 0
        lines = data.get("lines", 0) or 0
        prev_gross = by_month_sales.get(months[i - 1], {}).get("gross", 0) if i > 0 else None
        trend_pct = None
        if prev_gross and prev_gross > 0:
            trend_pct = (gross - prev_gross) / prev_gross * 100
        daily = data.get("daily_gross") or {}
        vals = list(daily.values()) if daily else []
        volatility = 0.0
        if len(vals) > 1 and sum(vals):
            mean = sum(vals) / len(vals)
            var = sum((x - mean) ** 2 for x in vals) / len(vals)
            volatility = sqrt(var) / mean * 100 if mean else 0
        avg_ticket = gross / lines if lines else None
        result[ym] = {
            "gross": round(gross, 2),
            "cog": round(cog, 2),
            "lines": lines,
            "trend_pct": round(trend_pct, 2) if trend_pct is not None else None,
            "volatility": round(volatility, 2),
            "avg_ticket": round(avg_ticket, 2) if avg_ticket is not None else None,
        }
    return result


def expense_metrics(by_cat_month: dict[tuple[int, int], dict[str, float]]) -> dict[tuple[int, int], dict]:
    """By (y,m): total_expense, labor, overhead, inventory, other, fixed_approx, variable_approx."""
    result = {}
    for ym, cats in by_cat_month.items():
        total = sum(cats.values())
        labor = cats.get("labor", 0)
        overhead = cats.get("overhead", 0)
        inventory = cats.get("inventory", 0)
        other = cats.get("other", 0)
        result[ym] = {
            "total_expense": round(total, 2),
            "labor": round(labor, 2),
            "overhead": round(overhead, 2),
            "inventory": round(inventory, 2),
            "other": round(other, 2),
        }
    return result


def margin_metrics(
    by_month_sales: dict,
    by_cat_month: dict[tuple[int, int], dict[str, float]],
    package_by_month: dict,
) -> dict[tuple[int, int], dict]:
    """By (y,m): revenue, cogs_proxy (from API + txn inventory), op_ex expense, gross_margin_pct, operating_margin_pct, confidence."""
    result = {}
    for ym in sorted(set(list(by_month_sales.keys()) + list(by_cat_month.keys()))):
        sales_data = by_month_sales.get(ym, {})
        revenue = sales_data.get("gross", 0) or 0
        cog_api = sales_data.get("cog", 0) or 0
        cats = by_cat_month.get(ym, {})
        inv_cost = cats.get("inventory", 0) or 0
        labor = cats.get("labor", 0) or 0
        overhead = cats.get("overhead", 0) or 0
        op_ex = labor + overhead
        cogs_proxy = cog_api if cog_api > 0 else inv_cost
        if cog_api > 0 and inv_cost > 0:
            cogs_proxy = cog_api  # prefer API
        gross_margin_pct = (revenue - cogs_proxy) / revenue * 100 if revenue else None
        operating_margin_pct = (revenue - cogs_proxy - op_ex) / revenue * 100 if revenue else None
        confidence = "confirmed" if cog_api > 0 else "estimated"
        cogs_source = "api" if cog_api > 0 else ("transaction" if inv_cost > 0 else "none")
        result[ym] = {
            "revenue": round(revenue, 2),
            "cogs_proxy": round(cogs_proxy, 2),
            "op_ex": round(op_ex, 2),
            "gross_margin_pct": round(gross_margin_pct, 2) if gross_margin_pct is not None else None,
            "operating_margin_pct": round(operating_margin_pct, 2) if operating_margin_pct is not None else None,
            "confidence": confidence,
            "cogs_source": cogs_source,
        }
    return result


def labor_metrics(by_cat_month: dict, by_month_sales: dict) -> dict[tuple[int, int], dict]:
    """By (y,m): labor_total, labor_pct_sales, trend."""
    result = {}
    months = sorted(set(list(by_cat_month.keys()) + list(by_month_sales.keys())))
    for i, ym in enumerate(months):
        labor = (by_cat_month.get(ym) or {}).get("labor", 0) or 0
        sales_data = by_month_sales.get(ym, {})
        gross = sales_data.get("gross", 0) or 0
        labor_pct = labor / gross * 100 if gross else None
        prev_labor = (by_cat_month.get(months[i - 1]) or {}).get("labor", 0) if i > 0 else 0
        trend = (labor - prev_labor) / prev_labor * 100 if prev_labor else None
        result[ym] = {
            "labor_total": round(labor, 2),
            "labor_pct_sales": round(labor_pct, 2) if labor_pct is not None else None,
            "labor_trend_pct": round(trend, 2) if trend is not None else None,
        }
    return result


def calculate_trend_metrics(
    sales_metrics_by_ym: dict,
    expense_metrics_by_ym: dict,
    labor_by_ym: dict,
    margin_by_ym: dict,
) -> dict[tuple[int, int], dict]:
    """
    Month-over-month trend percentages and interpretation.
    Returns by (y,m): sales_trend_pct, expense_trend_pct, labor_trend_pct, margin_trend_pct,
    plus interpretation: negative_sales_trend (sales down >15%), labor_pressure (labor >40% sales),
    margin_instability (op margin negative for this month; rolling 3-month in diagnosis).
    """
    months = sorted(set(
        list(sales_metrics_by_ym.keys()) +
        list(expense_metrics_by_ym.keys()) +
        list(labor_by_ym.keys()) +
        list(margin_by_ym.keys())
    ))
    result = {}
    for i, ym in enumerate(months):
        prev_ym = months[i - 1] if i > 0 else None
        s = sales_metrics_by_ym.get(ym, {})
        e = expense_metrics_by_ym.get(ym, {})
        L = labor_by_ym.get(ym, {})
        m = margin_by_ym.get(ym, {})

        sales_trend_pct = s.get("trend_pct")
        expense_trend_pct = None
        if prev_ym:
            prev_exp = (expense_metrics_by_ym.get(prev_ym) or {}).get("total_expense") or 0
            curr_exp = e.get("total_expense") or 0
            if prev_exp and prev_exp > 0:
                expense_trend_pct = (curr_exp - prev_exp) / prev_exp * 100
        labor_trend_pct = L.get("labor_trend_pct")
        margin_trend_pct = None
        if prev_ym:
            prev_op = (margin_by_ym.get(prev_ym) or {}).get("operating_margin_pct")
            curr_op = m.get("operating_margin_pct")
            if prev_op is not None and curr_op is not None:
                margin_trend_pct = curr_op - prev_op  # percentage point change

        labor_pct_sales = L.get("labor_pct_sales")
        op_margin = m.get("operating_margin_pct")
        negative_sales_trend = sales_trend_pct is not None and sales_trend_pct <= -15
        labor_pressure = labor_pct_sales is not None and labor_pct_sales > 40
        margin_instability = op_margin is not None and op_margin < 0

        result[ym] = {
            "sales_trend_pct": round(sales_trend_pct, 2) if sales_trend_pct is not None else None,
            "expense_trend_pct": round(expense_trend_pct, 2) if expense_trend_pct is not None else None,
            "labor_trend_pct": round(labor_trend_pct, 2) if labor_trend_pct is not None else None,
            "margin_trend_pct": round(margin_trend_pct, 2) if margin_trend_pct is not None else None,
            "negative_sales_trend": negative_sales_trend,
            "labor_pressure": labor_pressure,
            "margin_instability": margin_instability,
        }
    return result


def inventory_intelligence_metrics(
    by_month_sales: dict,
    by_cat_month: dict[tuple[int, int], dict[str, float]],
) -> dict[tuple[int, int], dict]:
    """
    By (y,m): inventory_turnover_estimate (revenue / inv_cost), inventory_sales_ratio (inv_cost / revenue),
    slow_inventory_indicator (True when inv_cost/revenue > 0.5 or ratio unusually high).
    """
    result = {}
    for ym in sorted(set(list(by_month_sales.keys()) + list(by_cat_month.keys()))):
        revenue = (by_month_sales.get(ym) or {}).get("gross") or 0
        inv_cost = (by_cat_month.get(ym) or {}).get("inventory") or 0
        if revenue and revenue > 0 and inv_cost and inv_cost > 0:
            turnover = revenue / inv_cost
            ratio = inv_cost / revenue
            slow = ratio > 0.5
        else:
            turnover = None
            ratio = inv_cost / revenue if revenue else None
            slow = bool(inv_cost and revenue and inv_cost / revenue > 0.5) if revenue else False
        result[ym] = {
            "inventory_turnover_estimate": round(turnover, 2) if turnover is not None else None,
            "inventory_sales_ratio": round(ratio, 4) if ratio is not None else None,
            "slow_inventory_indicator": slow,
        }
    return result


def sku_revenue_summary(normalized_items: list[dict]) -> list[dict]:
    """
    From order items: per SKU total gross, line count, months active.
    Returns list of dicts sorted by total_gross desc for top revenue; flag slow (low $ or single month).
    """
    from collections import defaultdict
    by_sku: dict[str, dict] = defaultdict(lambda: {"total_gross": 0.0, "lines": 0, "months": set()})
    for r in normalized_items:
        sku = (r.get("sku") or "").strip() or "(no sku)"
        by_sku[sku]["total_gross"] += r.get("gross", 0) or 0
        by_sku[sku]["lines"] += 1
        by_sku[sku]["months"].add(r.get("date_ym"))
    out = []
    for sku, data in by_sku.items():
        months_active = len(data["months"])
        total = data["total_gross"]
        out.append({
            "sku": sku,
            "total_gross": round(total, 2),
            "line_count": data["lines"],
            "months_active": months_active,
            "slow_selling": total < 500 or months_active <= 1,
        })
    out.sort(key=lambda x: -x["total_gross"])
    return out


def calculate_risk_score(
    margin_by_ym: dict,
    trend_metrics_by_ym: dict,
    anomaly_count_by_ym: dict[tuple[int, int], int],
    reconciliation_flagged_by_ym: dict[tuple[int, int], bool],
) -> dict[tuple[int, int], dict]:
    """
    Risk score 0-100 per month from margin, sales trend, expense growth, labor pressure, anomaly count.
    Returns by ym: risk_score (int), risk_category (healthy | watch closely | unstable | operational risk).
    Categories: 0-30 healthy, 31-60 watch closely, 61-80 unstable, 80+ operational risk.
    """
    result = {}
    for ym in sorted(set(
        list(margin_by_ym.keys()) +
        list(trend_metrics_by_ym.keys()) +
        list(anomaly_count_by_ym.keys())
    )):
        score = 0
        m = margin_by_ym.get(ym, {})
        t = trend_metrics_by_ym.get(ym, {})
        op_margin = m.get("operating_margin_pct")
        if op_margin is not None:
            if op_margin < -10:
                score += 40
            elif op_margin < 0:
                score += 25
            elif op_margin < 5:
                score += 10
        sales_trend = t.get("sales_trend_pct")
        if sales_trend is not None and sales_trend <= -15:
            score += 20
        expense_trend = t.get("expense_trend_pct")
        if expense_trend is not None and expense_trend > 25:
            score += 10
        if t.get("labor_pressure"):
            score += 15
        anom = anomaly_count_by_ym.get(ym, 0)
        score += min(anom * 5, 25)
        if reconciliation_flagged_by_ym.get(ym):
            score += 10
        score = min(100, max(0, score))
        if score <= 30:
            category = "healthy"
        elif score <= 60:
            category = "watch closely"
        elif score <= 80:
            category = "unstable"
        else:
            category = "operational risk"
        result[ym] = {"risk_score": score, "risk_category": category}
    return result


def health_rating(
    margin_metrics_by_ym: dict,
    anomaly_count_by_ym: dict[tuple[int, int], int],
    red_threshold: float = 0,
    yellow_threshold: float = 5,
) -> dict[tuple[int, int], str]:
    """green / yellow / red per month."""
    rating = {}
    for ym, m in margin_metrics_by_ym.items():
        op_margin = m.get("operating_margin_pct")
        anomalies = anomaly_count_by_ym.get(ym, 0)
        if op_margin is not None and op_margin < red_threshold:
            rating[ym] = "red"
        elif anomalies > 0 or (op_margin is not None and op_margin < yellow_threshold):
            rating[ym] = "yellow"
        else:
            rating[ym] = "green"
    return rating


def health_status_detailed(
    ym: tuple[int, int],
    margin_by_ym: dict,
    anomaly_count_by_ym: dict,
    reconciliation_flagged: bool,
    sales_trend_pct: float | None,
    anomalies_for_month: list[dict],
) -> dict[str, str]:
    """
    Returns status (healthy | watch closely | unstable | materially distorted),
    diagnosis, biggest_positive, biggest_negative, follow_up.
    """
    op_margin = (margin_by_ym.get(ym) or {}).get("operating_margin_pct")
    anom_count = anomaly_count_by_ym.get(ym, 0)
    if reconciliation_flagged and anom_count >= 3:
        status = "materially distorted by data issues"
    elif op_margin is not None and op_margin < -20:
        status = "unstable"
    elif anom_count > 0 or (op_margin is not None and op_margin < 5):
        status = "watch closely"
    else:
        status = "healthy"

    parts = []
    if op_margin is not None:
        parts.append(f"Op margin {op_margin:.1f}%")
    if anom_count > 0:
        metrics = [a.get("metric", "") for a in anomalies_for_month[:5]]
        parts.append(f"{anom_count} anomalies ({', '.join(metrics)})")
    diagnosis = "; ".join(parts) if parts else "—"

    positive = "—"
    if sales_trend_pct is not None and sales_trend_pct > 0:
        positive = f"Sales +{sales_trend_pct:.1f}% MoM"
    elif op_margin is not None and op_margin > 5:
        positive = f"Operating margin {op_margin:.1f}%"

    negative = "—"
    if op_margin is not None and op_margin < 0:
        negative = f"Operating margin {op_margin:.1f}%"
    if reconciliation_flagged and not negative.startswith("—"):
        negative += "; reconciliation delta"
    elif reconciliation_flagged:
        negative = "Reconciliation delta (POS vs bank)"

    follow_up = "—"
    if reconciliation_flagged:
        follow_up = "Reconcile POS vs bank deposits"
    elif anom_count > 0:
        follow_up = "Review anomaly report"
    return {
        "status": status,
        "diagnosis": diagnosis,
        "biggest_positive": positive,
        "biggest_negative": negative,
        "follow_up": follow_up,
    }
