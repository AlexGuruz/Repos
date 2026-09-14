from __future__ import annotations

from scripts.build_projection_dashboard_google_sheet import build_dashboard_data_values
from lib.projection_dashboard_sheet_rebuilt import (
    DASHBOARD_LAYOUT,
    build_dashboard_value_grid,
)


def _buy_plan_row(
    *,
    brand: str,
    category: str,
    allocated: str,
    avg_units_per_day: str,
    cash_recovery_days: str,
) -> dict[str, str]:
    return {
        "allocation_mode": "buy-plan",
        "brand": brand,
        "category": category,
        "allocated_cog_usd": allocated,
        "projected_revenue_from_allocated_units_usd": "300",
        "projected_gross_profit_usd": "120",
        "avg_units_per_day": avg_units_per_day,
        "cash_recovery_days": cash_recovery_days,
        "allocation_efficiency": "2.5",
    }


def _section(values: list[list[object]], title_prefix: str) -> tuple[list[object], list[object]]:
    for i, row in enumerate(values):
        if row and str(row[0]).startswith(title_prefix):
            return values[i + 1], values[i + 2]
    raise AssertionError(f"section not found: {title_prefix}")


def test_buy_plan_fast_section_exposes_avg_units_per_day() -> None:
    values, _meta = build_dashboard_data_values(
        [
            _buy_plan_row(
                brand="Slow Cash Day",
                category="Flower",
                allocated="100",
                avg_units_per_day="2",
                cash_recovery_days="1",
            ),
            _buy_plan_row(
                brand="Fast Velocity",
                category="Pre Roll",
                allocated="100",
                avg_units_per_day="10",
                cash_recovery_days="14",
            ),
        ]
    )

    header, first_row = _section(values, "FAST_VELOCITY_TOP_")

    assert header[6] == "avg_units_per_day"
    assert first_row[1] == "Fast Velocity"
    assert first_row[6] == 10.0


def test_buy_plan_fast_table_reads_velocity_column() -> None:
    values, meta = build_dashboard_data_values(
        [
            _buy_plan_row(
                brand="Fast Velocity",
                category="Pre Roll",
                allocated="100",
                avg_units_per_day="10",
                cash_recovery_days="14",
            )
        ]
    )
    header, first_row = _section(values, "FAST_VELOCITY_TOP_")
    assert header[6] == "avg_units_per_day"
    assert first_row[6] == 10.0

    grid, _layout_meta = build_dashboard_value_grid(
        meta=meta,
        kpis={
            "recovery_uses_days": True,
            "is_buy_plan": True,
            "total_pool": 100.0,
            "total_rev": 300.0,
            "total_gp": 120.0,
            "total_units_buy": 10.0,
            "w_avg_weeks": 1.0,
            "w_avg_cash_days": 14.0,
            "largest_txt": "Fast Velocity / Pre Roll",
            "fastest_major_txt": "Fast Velocity / Pre Roll",
            "high_gp_txt": "Fast Velocity / Pre Roll",
            "slow_dollars": 0.0,
            "hi_eff_txt": "Fast Velocity / Pre Roll",
            "lo_eff_txt": "Fast Velocity / Pre Roll",
        },
        kpi_col_letter="AC",
        kpi_start_row_1based=1,
        insight_bullets=[],
        action_signals=[],
        ledger_rows=[],
        subtitle_text="",
        initial_filter_mode="None",
        initial_filter_value="",
    )
    fastest = DASHBOARD_LAYOUT["fastest_recovery_table"]
    header_row = fastest.r0() + 1
    data_row = fastest.r0() + 2
    metric_col = fastest.c0() + 3

    assert grid[header_row][metric_col] == "Avg units / day"
    assert "INDEX(src,i,7)" in grid[data_row][metric_col]
