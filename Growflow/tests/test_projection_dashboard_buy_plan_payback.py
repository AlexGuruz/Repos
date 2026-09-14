from __future__ import annotations

from scripts.build_projection_dashboard_google_sheet import build_dashboard_data_values


def test_buy_plan_dashboard_helper_uses_gp_payback_days():
    rows = [
        {
            "allocation_mode": "buy-plan",
            "brand": "Brand A",
            "category": "Edibles",
            "allocated_cog_usd": "100",
            "projected_revenue_from_allocated_units_usd": "150",
            "projected_gross_profit_usd": "50",
            "cash_recovery_days": "14",
            "allocation_efficiency": "1.5",
        }
    ]

    values, meta = build_dashboard_data_values(rows)

    alloc_header = values[meta["alloc_header_row"]]
    alloc_row = values[meta["alloc_data_start"]]
    assert alloc_header[6] == "cog_payback_via_gp_days"
    assert alloc_row[6] == 28
