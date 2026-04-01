"""
Prioritized labor source: DB-ingested petty-cash payroll (primary), budget sheet (optional), transaction inference (fallback).
Prevents double counting; outputs labor_total, labor_source, confidence per month.
"""
from __future__ import annotations

import os
from typing import Any

from .sources import load_categories_config, load_sources_config

LABOR_SOURCE_DB = "db_petty_cash_payroll"
LABOR_SOURCE_PAYROLL_SHEET = "kylo_payroll_sheet"
LABOR_SOURCE_BUDGET = "kylo_budget"
LABOR_SOURCE_INFERENCE = "transaction_inference"

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_FALLBACK = "fallback"
CONFIDENCE_INFERRED = "inferred"


def _labor_patterns_from_categories() -> list[str]:
    """Extract labor description patterns from config/categories.yaml (same as categorization)."""
    cfg = load_categories_config() or {}
    patterns = []
    for r in (cfg.get("labor") or []):
        if not isinstance(r, dict):
            continue
        p = (r.get("pattern") or "").strip()
        if p:
            patterns.append(p)
    return patterns


def _db_labor_by_month(dsn: str, months_set: set[tuple[int, int]] | None) -> dict[tuple[int, int], dict[str, Any]]:
    """
    Query core.transactions_unified for labor (expense rows matching labor patterns); aggregate by month.
    Returns {(y, m): {labor_total: float, labor_source, confidence}} for months that have data.
    """
    try:
        import psycopg2
    except ImportError:
        return {}
    patterns = _labor_patterns_from_categories()
    if not patterns:
        return {}
    # Build WHERE: amount_cents < 0 AND (description ILIKE %p1% OR ...)
    placeholders = ["(description ILIKE %s)"] * len(patterns)
    pattern_params = [f"%{p}%" for p in patterns]
    cond = " OR ".join(placeholders)
    sql = f"""
    SELECT
      EXTRACT(YEAR FROM posted_date)::int AS y,
      EXTRACT(MONTH FROM posted_date)::int AS m,
      COALESCE(SUM(ABS(amount_cents)), 0) AS total_cents
    FROM core.transactions_unified
    WHERE amount_cents < 0 AND ({cond})
    GROUP BY 1, 2
    ORDER BY 1, 2
    """
    result = {}
    try:
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, pattern_params)
                for row in cur.fetchall():
                    y, m, total_cents = row
                    ym = (int(y), int(m))
                    if months_set is not None and ym not in months_set:
                        continue
                    result[ym] = {
                        "labor_total": round(total_cents / 100.0, 2),
                        "labor_source": LABOR_SOURCE_DB,
                        "confidence": CONFIDENCE_CONFIRMED,
                    }
        finally:
            conn.close()
    except Exception:
        return {}
    return result


def get_labor_by_month(
    by_cat_month: dict[tuple[int, int], dict[str, float]],
    months_set: set[tuple[int, int]] | None = None,
    *,
    database_dsn: str | None = None,
    payroll_sheet_labor_by_month: dict[tuple[int, int], float] | None = None,
    budget_labor_by_month: dict[tuple[int, int], float] | None = None,
) -> dict[tuple[int, int], dict[str, Any]]:
    """
    Prioritized labor per month: DB petty-cash payroll → Kylo PAYROLL sheet → kylo_budget → transaction_inference.
    Prevents double counting: one source per month.

    Returns:
        {(y, m): {labor_total: float, labor_source: str, confidence: str}}
    """
    if months_set is None:
        months_set = set(by_cat_month.keys())
    out: dict[tuple[int, int], dict[str, Any]] = {}

    # 1) DB primary
    cfg = load_sources_config() or {}
    labor_cfg = cfg.get("labor")
    if not isinstance(labor_cfg, dict):
        labor_cfg = {}
    dsn = database_dsn or labor_cfg.get("database_dsn")
    if not dsn:
        dsn = os.environ.get("KYLO_GLOBAL_DSN")
    db_labor = _db_labor_by_month(dsn, months_set) if dsn else {}

    # 2) Kylo PAYROLL tab (per-year sheet)
    payroll_sheet = payroll_sheet_labor_by_month or {}

    # 3) Budget (optional)
    budget = budget_labor_by_month or {}

    # 4) Transaction inference from by_cat_month
    for ym in months_set:
        labor_total = 0.0
        source = LABOR_SOURCE_INFERENCE
        confidence = CONFIDENCE_INFERRED
        if ym in db_labor:
            labor_total = db_labor[ym]["labor_total"]
            source = LABOR_SOURCE_DB
            confidence = CONFIDENCE_CONFIRMED
        elif ym in payroll_sheet and (payroll_sheet[ym] or 0) != 0:
            labor_total = float(payroll_sheet[ym])
            source = LABOR_SOURCE_PAYROLL_SHEET
            confidence = CONFIDENCE_CONFIRMED
        elif ym in budget and (budget[ym] or 0) != 0:
            labor_total = float(budget[ym])
            source = LABOR_SOURCE_BUDGET
            confidence = CONFIDENCE_FALLBACK
        else:
            labor_total = (by_cat_month.get(ym) or {}).get("labor", 0) or 0
        out[ym] = {
            "labor_total": round(labor_total, 2),
            "labor_source": source,
            "confidence": confidence,
        }
    return out


def merge_labor_into_by_cat_month(
    by_cat_month: dict[tuple[int, int], dict[str, float]],
    labor_by_month: dict[tuple[int, int], dict[str, Any]],
) -> dict[tuple[int, int], dict[str, float]]:
    """
    Return a copy of by_cat_month with labor replaced by prioritized labor_by_month totals.
    Use this for expense_metrics, margin_metrics, labor_metrics so all use the same labor source.
    """
    from copy import deepcopy
    adj = deepcopy(by_cat_month)
    for ym, lab in labor_by_month.items():
        if ym not in adj:
            adj[ym] = {}
        adj[ym]["labor"] = lab.get("labor_total", 0)
    return adj
