"""
Layer 2: Apply category rules to normalized transactions.
"""
from __future__ import annotations

from typing import Any

from .sources import load_categories_config


def _build_rules() -> tuple[list[tuple[str, str, str, bool | None]], list[tuple[str, str, str, bool | None]]]:
    """(income_rules, expense_rules). Each rule: (pattern_upper, category, subcategory, fixed)."""
    cfg = load_categories_config()
    income_r: list[tuple[str, str, str, bool | None]] = []
    labor_r: list[tuple[str, str, str, bool | None]] = []
    inventory_r: list[tuple[str, str, str, bool | None]] = []
    overhead_r: list[tuple[str, str, str, bool | None]] = []

    for cat_key, rule_list in (cfg or {}).items():
        if not isinstance(rule_list, list):
            continue
        for r in rule_list:
            if not isinstance(r, dict):
                continue
            pattern = (r.get("pattern") or "").strip().upper()
            sub = (r.get("subcategory") or "").strip() or "other"
            fixed = r.get("fixed") if isinstance(r.get("fixed"), bool) else None
            if not pattern:
                continue
            t = (pattern, cat_key, sub, fixed)
            if cat_key == "income":
                income_r.append(t)
            elif cat_key == "labor":
                labor_r.append(t)
            elif cat_key == "inventory":
                inventory_r.append(t)
            elif cat_key == "overhead":
                overhead_r.append(t)

    # Sort by pattern length desc so longer matches first
    def sort_key(x: tuple) -> int:
        return -len(x[0])

    income_r.sort(key=sort_key)
    expense_order = labor_r + inventory_r + overhead_r
    expense_order.sort(key=sort_key)
    return income_r, expense_order


def categorize_transaction(amount: float, source_upper: str, income_r: list = None, expense_r: list = None) -> dict[str, Any]:
    """Return { category, subcategory, confidence, fixed_variable }. confidence: high/medium/low."""
    if income_r is None or expense_r is None:
        income_r, expense_r = _build_rules()
    if amount > 0:
        for pattern, category, subcategory, _ in income_r:
            if pattern in source_upper:
                return {"category": category, "subcategory": subcategory, "confidence": "high", "fixed_variable": None}
        return {"category": "income", "subcategory": "other", "confidence": "low", "fixed_variable": None}
    # Expense
    for pattern, category, subcategory, fixed in expense_r:
        if pattern in source_upper:
            return {"category": category, "subcategory": subcategory, "confidence": "high", "fixed_variable": fixed}
    return {"category": "other", "subcategory": "uncategorized", "confidence": "low", "fixed_variable": None}


def apply_categorization(normalized_transactions: list[dict]) -> list[dict]:
    """Add category, subcategory, confidence, fixed_variable to each row."""
    income_r, expense_r = _build_rules()
    out = []
    for row in normalized_transactions:
        r = dict(row)
        amt = r.get("amount", 0)
        src = r.get("source_upper", "")
        tag = categorize_transaction(amt, src, income_r=income_r, expense_r=expense_r)
        r["category"] = tag["category"]
        r["subcategory"] = tag["subcategory"]
        r["confidence"] = tag["confidence"]
        r["fixed_variable"] = tag["fixed_variable"]
        out.append(r)
    return out


def aggregate_by_category_month(tagged: list[dict]) -> dict[tuple[int, int], dict[str, float]]:
    """{(y,m): { category: total_abs_amount, ... }}. Only expenses (amount < 0) for category totals."""
    from collections import defaultdict
    by_ym: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in tagged:
        if row.get("amount", 0) >= 0:
            continue
        k = row["date_ym"]
        cat = row.get("category", "other")
        by_ym[k][cat] += abs(row["amount"])
    return {k: dict(v) for k, v in by_ym.items()}


def aggregate_income_by_month(tagged: list[dict]) -> dict[tuple[int, int], float]:
    """{(y,m): total_income}."""
    from collections import defaultdict
    by_ym: dict[tuple[int, int], float] = defaultdict(float)
    for row in tagged:
        if row.get("amount", 0) <= 0:
            continue
        if row.get("category") != "income":
            continue
        by_ym[row["date_ym"]] += row["amount"]
    return dict(by_ym)


def aggregate_income_by_subcategory_by_month(tagged: list[dict]) -> dict[tuple[int, int], dict[str, float]]:
    """{(y,m): { subcategory: total }} for positive income rows only."""
    from collections import defaultdict
    by_ym: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in tagged:
        if row.get("amount", 0) <= 0:
            continue
        if row.get("category") != "income":
            continue
        sub = (row.get("subcategory") or "other").strip() or "other"
        by_ym[row["date_ym"]][sub] += row["amount"]
    return {k: dict(v) for k, v in by_ym.items()}


def aggregate_overhead_by_subcategory_by_month(tagged: list[dict]) -> dict[tuple[int, int], dict[str, float]]:
    """
    {(y,m): { subcategory: total }} for overhead expense rows only.
    Inferred from cleaned Transactions/Bank descriptions (Project-Kylo); each row's
    description is matched to categories.yaml to assign bill type (rent, utilities, etc.).
    """
    from collections import defaultdict
    by_ym: dict[tuple[int, int], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in tagged:
        if row.get("amount", 0) >= 0:
            continue
        if row.get("category") != "overhead":
            continue
        sub = (row.get("subcategory") or "other").strip() or "other"
        by_ym[row["date_ym"]][sub] += abs(row["amount"])
    return {k: dict(v) for k, v in by_ym.items()}
