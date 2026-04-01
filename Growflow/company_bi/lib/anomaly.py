"""
Layer 5 (part): Anomaly detection — apply thresholds and flag issues.
"""
from __future__ import annotations

from typing import Any

from .reconcile import reconcile_monthly


def run_anomalies(
    by_month_sales: dict,
    by_cat_month: dict,
    income_by_month: dict,
    margin_by_ym: dict,
    reconciliation_rows: list[dict],
    config: dict,
) -> tuple[list[dict[str, Any]], dict[tuple[int, int], int]]:
    """
    Returns (list of anomaly rows, anomaly_count_by_ym).
    config: anomaly.reconciliation_diff_dollars, expense_mom_pct, expense_mom_dollars, sales_drop_pct, margin_red_threshold_pct, margin_yellow_threshold_pct, labor_pressure_pct.
    """
    thresh = config.get("anomaly", {})
    diff_dollars = thresh.get("reconciliation_diff_dollars", 500)
    expense_mom_pct = thresh.get("expense_mom_pct", 25)
    expense_mom_dollars = thresh.get("expense_mom_dollars", 500)
    sales_drop_pct = thresh.get("sales_drop_pct", 15)
    margin_red = thresh.get("margin_red_threshold_pct", 0)
    margin_yellow = thresh.get("margin_yellow_threshold_pct", 5)
    labor_pressure_pct = thresh.get("labor_pressure_pct", 30)

    anomalies: list[dict[str, Any]] = []
    count_by_ym: dict[tuple[int, int], int] = {}

    # Reconciliation
    for r in reconciliation_rows:
        if r.get("flagged"):
            ym = (r["year"], r["month"])
            anomalies.append({
                "date_ym": ym,
                "metric": "reconciliation",
                "value": r["difference"],
                "prior_value": None,
                "threshold": diff_dollars,
                "note": r.get("note", ""),
            })
            count_by_ym[ym] = count_by_ym.get(ym, 0) + 1

    # Expense MoM
    months = sorted(by_cat_month.keys())
    for i, ym in enumerate(months):
        if i == 0:
            continue
        prev_ym = months[i - 1]
        curr_cats = by_cat_month.get(ym, {})
        prev_cats = by_cat_month.get(prev_ym, {})
        for cat in ("labor", "overhead", "inventory", "other"):
            c_curr = curr_cats.get(cat, 0) or 0
            c_prev = prev_cats.get(cat, 0) or 0
            if c_prev == 0:
                continue
            pct = (c_curr - c_prev) / c_prev * 100
            if pct >= expense_mom_pct or (c_curr - c_prev) >= expense_mom_dollars:
                anomalies.append({
                    "date_ym": ym,
                    "metric": f"expense_mom_{cat}",
                    "value": c_curr,
                    "prior_value": c_prev,
                    "threshold": f"{expense_mom_pct}% or ${expense_mom_dollars}",
                    "note": f"{cat} increased {pct:.1f}% or ${c_curr - c_prev:.2f}",
                })
                count_by_ym[ym] = count_by_ym.get(ym, 0) + 1

    # Sales drop (by_month_sales has gross/cog/lines/daily_gross; trend not in it — compute MoM)
    months_sales = sorted((by_month_sales or {}).keys())
    for i, ym in enumerate(months_sales):
        if i == 0:
            continue
        data = (by_month_sales or {}).get(ym, {})
        prev_ym = months_sales[i - 1]
        prev_gross = (by_month_sales or {}).get(prev_ym, {}).get("gross") or 0
        gross = data.get("gross") or 0
        trend = (gross - prev_gross) / prev_gross * 100 if prev_gross else None
        if trend is not None and trend <= -sales_drop_pct:
            anomalies.append({
                "date_ym": ym,
                "metric": "sales_drop",
                "value": gross,
                "prior_value": prev_gross,
                "threshold": f"{sales_drop_pct}%",
                "note": f"Sales down {abs(trend):.1f}% MoM",
            })
            count_by_ym[ym] = count_by_ym.get(ym, 0) + 1

    # Margin
    for ym, m in (margin_by_ym or {}).items():
        op = m.get("operating_margin_pct")
        if op is not None:
            if op < margin_red:
                anomalies.append({
                    "date_ym": ym,
                    "metric": "margin",
                    "value": op,
                    "prior_value": None,
                    "threshold": margin_red,
                    "note": f"Operating margin {op:.1f}% below red threshold",
                })
                count_by_ym[ym] = count_by_ym.get(ym, 0) + 1
            elif op < margin_yellow:
                anomalies.append({
                    "date_ym": ym,
                    "metric": "margin",
                    "value": op,
                    "prior_value": None,
                    "threshold": margin_yellow,
                    "note": f"Operating margin {op:.1f}% below yellow threshold",
                })
                count_by_ym[ym] = count_by_ym.get(ym, 0) + 1

    return anomalies, count_by_ym
