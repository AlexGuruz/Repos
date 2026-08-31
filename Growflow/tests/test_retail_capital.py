"""Tests for retail capital payload builder."""
from __future__ import annotations

from lib.retail_dashboard.capital import build_capital, payload_to_dict


def _row(**kwargs) -> dict[str, str]:
    base = {
        "allocation_mode": "buy-plan",
        "velocity_window_days_run": "49",
        "cash_cycle_days_run": "14",
        "remaining_pool_unallocated_usd": "500.00",
        "brand": "BrandA",
        "category": "Flower",
        "allocated_cog_usd": "1000.00",
        "trailing_units_sold": "100",
        "avg_units_per_week": "5",
        "weeks_to_sell_through": "4",
        "projected_revenue_from_allocated_units_usd": "2000.00",
        "projected_gross_profit_usd": "1000.00",
        "allocation_efficiency": "2.00",
        "avg_units_per_day": "1.5",
        "cash_recovery_days": "10",
        "cash_cycle_status": "SAFE",
        "units_from_allocation": "50",
        "cover_status": "HEALTHY",
    }
    base.update({k: str(v) for k, v in kwargs.items()})
    return base


def test_build_capital_from_rows():
    rows = [
        _row(brand="BrandA", category="Flower", allocated_cog_usd="1200.00", projected_gross_profit_usd="800.00"),
        _row(brand="BrandB", category="Edibles", allocated_cog_usd="800.00", projected_gross_profit_usd="600.00",
             cash_recovery_days="25", cash_cycle_status="CAPITAL RISK"),
    ]
    payload = build_capital(rows)
    d = payload_to_dict(payload)
    assert d["meta"]["row_count"] == 2
    assert d["meta"]["validation"]["ok"] is True
    assert len(d["kpi_banner"]) >= 4
    assert d["charts"]["pool_by_category"]
    assert d["tables"]["ledger"]
    assert d["scenario"]["remaining_unallocated_usd"] == 500.0
    assert d["scenario"]["pool_usd"] == 2500.0  # 2000 deployed + 500 unallocated


def test_empty_capital():
    payload = build_capital([])
    assert payload.meta["validation"]["ok"] is False
    assert "layer2_csv_missing" in payload.meta["validation"]["errors"]
