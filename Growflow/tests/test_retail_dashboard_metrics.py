"""Golden-fixture tests for retail dashboard metrics."""
from __future__ import annotations

from datetime import date

from lib.retail_dashboard.metrics import build_dashboard, validate_sums


def _line(
    *,
    line_id: str,
    order_id: str,
    sold_date: str,
    budtender: str,
    brand: str,
    category: str,
    gross: int,
    net: int,
    discount: int,
    menu: int,
    cog: int = 0,
    landed: int | None = None,
    is_return: int = 0,
    channel: str = "in_store",
):
    return {
        "object_id": line_id,
        "sold_date_local": sold_date,
        "order_object_id": order_id,
        "budtender_name": budtender,
        "brand_canonical": brand,
        "brand_raw": brand,
        "category_canonical": category,
        "gross_price_cents": gross,
        "net_price_cents": net,
        "discount_cents": discount,
        "original_price_cents": menu,
        "price_cents": net,
        "collected_otd_cents": net,
        "cog_cents": cog,
        "landed_cost_cents": landed,
        "is_return": is_return,
        "channel": channel,
    }


def test_build_dashboard_sums_reconcile():
    lines = [
        _line(line_id="l1", order_id="o1", sold_date="2026-06-01", budtender="Alice", brand="A", category="Flower",
              gross=2000, net=1800, discount=200, menu=2000, cog=800, landed=900),
        _line(line_id="l2", order_id="o2", sold_date="2026-06-01", budtender="Bob", brand="B", category="Edibles",
              gross=1000, net=1000, discount=0, menu=1000, cog=400, landed=450),
        _line(line_id="l3", order_id="o3", sold_date="2026-06-02", budtender="Alice", brand="A", category="Flower",
              gross=1500, net=1200, discount=300, menu=1500, cog=600, landed=650),
    ]
    payload = build_dashboard(
        lines,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 2),
    )
    assert payload.meta["store_net_sales"] == 40.0  # 18 + 10 + 12
    assert len(payload.budtender_sales) == 2
    assert payload.budtender_sales[0]["budtender"] == "Alice"
    assert payload.budtender_sales[0]["net_sales"] == 30.0
    assert len(payload.discounts_over_time) == 2
    assert validate_sums(payload) == []


def test_compare_prior_period():
    lines = [
        _line(line_id="l1", order_id="o1", sold_date="2026-06-08", budtender="A", brand="X", category="C",
              gross=1000, net=1000, discount=0, menu=1000),
        _line(line_id="l2", order_id="o2", sold_date="2026-06-01", budtender="A", brand="X", category="C",
              gross=500, net=500, discount=0, menu=500),
    ]
    payload = build_dashboard(
        lines,
        period_start=date(2026, 6, 8),
        period_end=date(2026, 6, 8),
        prior_start=date(2026, 6, 1),
        prior_end=date(2026, 6, 1),
    )
    assert payload.period_compare_kpis
    net_kpi = next(k for k in payload.period_compare_kpis if k["key"] == "net_sales")
    assert net_kpi["current"] == 10.0
    assert net_kpi["prior"] == 5.0
