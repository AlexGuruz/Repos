"""
Layer 5: Build output tables for dashboard, anomaly report, expense report, margin report, etc.
"""
from __future__ import annotations

from typing import Any

from .metrics import health_status_detailed


def _month_label(ym: tuple[int, int]) -> str:
    from datetime import datetime
    return datetime(ym[0], ym[1], 1).strftime("%b %Y")


def build_monthly_dashboard(
    sales_metrics_by_ym: dict,
    expense_metrics_by_ym: dict,
    margin_by_ym: dict,
    health_by_ym: dict,
    anomaly_count_by_ym: dict,
    anomalies: list[dict] | None = None,
    reconciliation_rows: list[dict] | None = None,
    trend_metrics_by_ym: dict | None = None,
    risk_metrics_by_ym: dict | None = None,
    labor_by_ym: dict | None = None,
) -> list[list[Any]]:
    """Rows for BI Monthly Dashboard: Sales, POS income, Expenses, Labor, Overhead, COGS, margins, trends, Risk score, Status, Diagnosis, Follow-up."""
    months = sorted(set(
        list(sales_metrics_by_ym.keys()) +
        list(expense_metrics_by_ym.keys()) +
        list(margin_by_ym.keys())
    ))
    recon_by_ym = {}
    if reconciliation_rows:
        for r in reconciliation_rows:
            recon_by_ym[(r["year"], r["month"])] = r
    anomalies_by_ym: dict[tuple[int, int], list] = {}
    if anomalies:
        for a in anomalies:
            ym = a.get("date_ym")
            if ym:
                anomalies_by_ym.setdefault(ym, []).append(a)
    trend_metrics_by_ym = trend_metrics_by_ym or {}
    risk_metrics_by_ym = risk_metrics_by_ym or {}
    labor_by_ym = labor_by_ym or {}

    rows = [[
        "Month", "Sales", "POS income", "Total expense", "Labor", "Labor source", "Overhead", "Inventory cost", "COGS",
        "Gross margin %", "Operating margin %", "Health", "Anomalies",
        "Sales trend %", "Expense trend %", "Labor trend %", "Margin trend %",
        "Risk score", "Risk category",
        "Status", "Diagnosis", "Biggest positive", "Biggest negative", "Follow-up",
    ]]
    for ym in months:
        s = sales_metrics_by_ym.get(ym, {})
        e = expense_metrics_by_ym.get(ym, {})
        m = margin_by_ym.get(ym, {})
        h = health_by_ym.get(ym, "—")
        anom = anomaly_count_by_ym.get(ym, 0)
        recon = recon_by_ym.get(ym, {})
        recon_flagged = recon.get("flagged", False)
        pos_income = recon.get("pos_comparable_income")
        anom_list = anomalies_by_ym.get(ym, [])
        trend = s.get("trend_pct")
        diag = health_status_detailed(
            ym, margin_by_ym, anomaly_count_by_ym, recon_flagged, trend, anom_list,
        )
        t = trend_metrics_by_ym.get(ym, {})
        risk = risk_metrics_by_ym.get(ym, {})
        labor_source = (labor_by_ym.get(ym) or {}).get("labor_source") or "—"
        rows.append([
            _month_label(ym),
            s.get("gross"),
            pos_income,
            e.get("total_expense"),
            e.get("labor"),
            labor_source or "—",
            e.get("overhead"),
            e.get("inventory"),
            m.get("cogs_proxy"),
            m.get("gross_margin_pct"),
            m.get("operating_margin_pct"),
            h,
            anom,
            t.get("sales_trend_pct"),
            t.get("expense_trend_pct"),
            t.get("labor_trend_pct"),
            t.get("margin_trend_pct"),
            risk.get("risk_score"),
            risk.get("risk_category", "—"),
            diag.get("status", "—"),
            diag.get("diagnosis", "—"),
            diag.get("biggest_positive", "—"),
            diag.get("biggest_negative", "—"),
            diag.get("follow_up", "—"),
        ])
    return rows


def build_anomaly_report(anomalies: list[dict]) -> list[list[Any]]:
    """Rows: Month, Metric, Value, Prior, Threshold, Note."""
    rows = [["Month", "Metric", "Value", "Prior value", "Threshold", "Note"]]
    for a in sorted(anomalies, key=lambda x: (x.get("date_ym") or (0, 0))):
        ym = a.get("date_ym") or (0, 0)
        rows.append([
            _month_label(ym),
            a.get("metric", ""),
            a.get("value"),
            a.get("prior_value"),
            a.get("threshold"),
            a.get("note", ""),
        ])
    return rows


def build_expense_category_report(by_cat_month: dict) -> list[list[Any]]:
    """Rows: Month, Category, Amount, % of total expense."""
    months = sorted(by_cat_month.keys())
    rows = [["Month", "Category", "Amount", "% of expense"]]
    for ym in months:
        cats = by_cat_month.get(ym, {})
        total = sum(cats.values()) or 1
        for cat, amt in sorted(cats.items(), key=lambda x: -abs(x[1])):
            pct = amt / total * 100 if total else 0
            rows.append([_month_label(ym), cat, round(amt, 2), round(pct, 2)])
    return rows


def build_recurring_bills_report(overhead_by_subcategory_by_month: dict) -> list[list[Any]]:
    """
    Rows: Month, Bill type (subcategory), Amount, % of overhead.
    Inferred from cleaned Transactions/Bank (Project-Kylo) via categories.yaml patterns:
    rent, utilities, insurance, subscriptions, compliance, bank_fees, transfer, credit_card, etc.
    """
    months = sorted(overhead_by_subcategory_by_month.keys())
    rows = [["Month", "Bill type", "Amount", "% of overhead"]]
    for ym in months:
        subs = overhead_by_subcategory_by_month.get(ym, {})
        total = sum(subs.values()) or 1
        for bill_type, amt in sorted(subs.items(), key=lambda x: -abs(x[1])):
            pct = amt / total * 100 if total else 0
            rows.append([_month_label(ym), bill_type, round(amt, 2), round(pct, 2)])
    return rows


def build_margin_report(margin_by_ym: dict) -> list[list[Any]]:
    """Rows: Month, Revenue, COGS proxy, COGS source, OpEx, Gross margin %, Operating margin %, Confidence."""
    rows = [["Month", "Revenue", "COGS proxy", "COGS source", "OpEx", "Gross margin %", "Operating margin %", "Confidence"]]
    for ym in sorted(margin_by_ym.keys()):
        m = margin_by_ym[ym]
        rows.append([
            _month_label(ym),
            m.get("revenue"),
            m.get("cogs_proxy"),
            m.get("cogs_source", ""),
            m.get("op_ex"),
            m.get("gross_margin_pct"),
            m.get("operating_margin_pct"),
            m.get("confidence", ""),
        ])
    return rows


def build_reconciliation_report(reconciliation_rows: list[dict]) -> list[list[Any]]:
    """Rows: Month, GrowFlow sales, Recorded income, POS-comparable income, Difference, Delta vs GrowFlow, Flagged, Note, Likely cause, Confidence."""
    rows = [
        [
            "Month",
            "GrowFlow sales",
            "Recorded income",
            "POS-comparable income",
            "Difference",
            "Delta vs GrowFlow",
            "Flagged",
            "Note",
            "Likely cause",
            "Confidence",
        ]
    ]
    for r in reconciliation_rows:
        rows.append([
            _month_label((r["year"], r["month"])),
            r.get("growflow_sales"),
            r.get("recorded_income"),
            r.get("pos_comparable_income"),
            r.get("difference"),
            r.get("difference_pos"),
            "Y" if r.get("flagged") else "N",
            r.get("note", ""),
            r.get("likely_cause", ""),
            r.get("confidence", ""),
        ])
    return rows


def build_labor_report(labor_by_ym: dict) -> list[list[Any]]:
    """Rows: Month, Labor total, Labor % of sales, Labor trend %, Labor source, Confidence."""
    rows = [["Month", "Labor total", "Labor % of sales", "Labor trend %", "Labor source", "Confidence"]]
    for ym in sorted(labor_by_ym.keys()):
        L = labor_by_ym[ym]
        rows.append([
            _month_label(ym),
            L.get("labor_total"),
            L.get("labor_pct_sales"),
            L.get("labor_trend_pct"),
            L.get("labor_source", ""),
            L.get("confidence", ""),
        ])
    return rows


def build_inventory_analysis(
    inventory_metrics_by_ym: dict,
    sku_summary: list[dict],
) -> list[list[Any]]:
    """Rows for inventory_analysis.csv: monthly block (Month, inventory_turnover_estimate, inventory_sales_ratio, slow_inventory_indicator), then SKU block (sku, total_gross, line_count, months_active, slow_selling)."""
    rows = [["Month", "inventory_turnover_estimate", "inventory_sales_ratio", "slow_inventory_indicator"]]
    for ym in sorted(inventory_metrics_by_ym.keys()):
        inv = inventory_metrics_by_ym[ym]
        rows.append([
            _month_label(ym),
            inv.get("inventory_turnover_estimate"),
            inv.get("inventory_sales_ratio"),
            "Y" if inv.get("slow_inventory_indicator") else "N",
        ])
    rows.append([])
    rows.append(["sku", "total_gross", "line_count", "months_active", "slow_selling"])
    for s in sku_summary:
        rows.append([
            s.get("sku", ""),
            s.get("total_gross"),
            s.get("line_count"),
            s.get("months_active"),
            "Y" if s.get("slow_selling") else "N",
        ])
    return rows
