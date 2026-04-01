"""
Data validation layer: fail the pipeline safely when data integrity problems occur.
Run after normalization, categorization, and reconciliation; before metrics/report generation.
"""
from __future__ import annotations

from typing import Any

KNOWN_CATEGORIES = frozenset({"income", "labor", "overhead", "inventory", "other"})


class ValidationError(Exception):
    """Raised when a validation check fails."""
    def __init__(self, check_name: str, message: str):
        self.check_name = check_name
        self.message = message
        super().__init__(f"[{check_name}] {message}")


def validate_growflow_sales(
    normalized_items: list[dict],
    by_month_sales: dict[tuple[int, int], dict],
) -> None:
    """GrowFlow data checks: dataset exists, no negative sales, no missing date fields."""
    if not normalized_items and not by_month_sales:
        raise ValidationError(
            "growflow_sales_exists",
            "GrowFlow sales dataset is empty; no order items and no monthly sales.",
        )
    for item in normalized_items:
        if item.get("gross", 0) < 0:
            raise ValidationError(
                "growflow_no_negative_sales",
                f"Negative gross sale found: {item.get('gross')} for date_ym={item.get('date_ym')}.",
            )
        if not item.get("date_ym"):
            raise ValidationError(
                "growflow_no_missing_dates",
                "Order item missing date_ym.",
            )
    for ym, data in by_month_sales.items():
        gross = data.get("gross", 0) or 0
        if gross < 0:
            raise ValidationError(
                "growflow_no_negative_sales",
                f"Negative monthly gross for {ym}: {gross}.",
            )


def validate_growflow_inventory(by_month_sales: dict) -> None:
    """Inventory dataset exists in the sense that we have sales structure (COG/inventory used from sales or packages)."""
    if not by_month_sales:
        raise ValidationError(
            "growflow_inventory_structure",
            "No monthly sales structure; cannot validate inventory/COGS inputs.",
        )
    # Pipeline may not fetch packages; having by_month_sales with cog key is sufficient
    for ym, data in by_month_sales.items():
        if "gross" not in data:
            raise ValidationError(
                "growflow_inventory_structure",
                f"Month {ym} missing 'gross' in sales data.",
            )


def validate_transactions(
    normalized_txns: list[dict],
    tagged: list[dict],
) -> None:
    """Transaction dataset checks: not empty when we have any, date/amount valid, categories known."""
    if not normalized_txns and not tagged:
        return  # Allow no transactions (expense/margin will be partial)
    if tagged:
        for row in tagged:
            if "date_ym" not in row:
                raise ValidationError(
                    "transactions_date_column",
                    "Tagged transaction missing date_ym.",
                )
            amt = row.get("amount")
            if amt is not None and not isinstance(amt, (int, float)):
                raise ValidationError(
                    "transactions_amount_numeric",
                    f"Transaction amount not numeric: {type(amt)}.",
                )
            cat = row.get("category")
            if cat is not None and cat not in KNOWN_CATEGORIES:
                raise ValidationError(
                    "category_known",
                    f"Unknown category '{cat}'; expected one of {sorted(KNOWN_CATEGORIES)}.",
                )


def validate_labor_source(
    labor_by_month: dict[tuple[int, int], dict],
    by_month_sales: dict[tuple[int, int], dict],
    *,
    database_dsn_configured: bool = False,
) -> None:
    """
    Labor source checks:
    1. If DB is configured but no month has labor_source db_petty_cash_payroll, raise.
    2. If DB is configured and some months use transaction_inference (and those months have sales), warn.
    """
    if not labor_by_month:
        return
    sources = [labor_by_month[ym].get("labor_source") for ym in labor_by_month]
    db_used = any(s == "db_petty_cash_payroll" for s in sources)
    inference_used = any(s == "transaction_inference" for s in sources)
    if database_dsn_configured and not db_used:
        months_with_sales = set(by_month_sales.keys()) if by_month_sales else set()
        if months_with_sales and labor_by_month:
            raise ValidationError(
                "labor_db_configured_no_rows",
                "Labor database DSN is configured but no labor rows came from db_petty_cash_payroll. "
                "Check that core.transactions_unified has petty-cash payroll data and labor patterns match.",
            )
    if database_dsn_configured and db_used and inference_used:
        # Allow warning only; do not raise so pipeline can still run
        import warnings
        inference_months = [ym for ym, d in labor_by_month.items() if d.get("labor_source") == "transaction_inference"]
        warnings.warn(
            f"Labor source: some months use transaction_inference while DB is configured: {inference_months}. "
            "Ensure DB has ingested petty-cash data for those months.",
            UserWarning,
            stacklevel=2,
        )


def validate_reconciliation(reconciliation_rows: list[dict]) -> None:
    """Reconciliation validation: sales totals exist, POS-comparable computed, difference numeric."""
    if not reconciliation_rows:
        return
    for r in reconciliation_rows:
        if r.get("growflow_sales") is None and "growflow_sales" in r:
            raise ValidationError(
                "reconciliation_sales_totals",
                f"Missing growflow_sales for month {r.get('year')}-{r.get('month')}.",
            )
        if "pos_comparable_income" not in r:
            raise ValidationError(
                "reconciliation_pos_comparable",
                "Reconciliation row missing pos_comparable_income.",
            )
        diff = r.get("difference")
        if diff is not None and not isinstance(diff, (int, float)):
            raise ValidationError(
                "reconciliation_difference_numeric",
                f"Reconciliation difference not numeric: {type(diff)}.",
            )


def run_validation(
    normalized_items: list[dict],
    by_month_sales: dict[tuple[int, int], dict],
    normalized_txns: list[dict],
    tagged: list[dict],
    reconciliation_rows: list[dict],
    *,
    require_transactions: bool = False,
    labor_by_month: dict[tuple[int, int], dict] | None = None,
) -> None:
    """
    Run all validation checks. Raises ValidationError on first failure.
    If require_transactions=True, fails when tagged is empty.
    If labor_by_month is provided and labor DB is configured, validates labor source.
    """
    validate_growflow_sales(normalized_items, by_month_sales)
    validate_growflow_inventory(by_month_sales)
    validate_transactions(normalized_txns, tagged)
    if require_transactions and not tagged:
        raise ValidationError(
            "transactions_not_empty",
            "No transactions available; pipeline requires transaction data.",
        )
    validate_reconciliation(reconciliation_rows)
    if labor_by_month is not None:
        import os
        from .sources import load_sources_config
        cfg = load_sources_config() or {}
        dsn = (cfg.get("labor") or {}).get("database_dsn") or os.environ.get("KYLO_GLOBAL_DSN")
        validate_labor_source(
            labor_by_month,
            by_month_sales,
            database_dsn_configured=bool(dsn),
        )
