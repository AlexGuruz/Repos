"""Tests for brand exclusion parsing in projection script."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# Import module under test by path to avoid scripts package issues
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "build_projection",
    REPO / "scripts" / "build_projection_by_category_brand.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_utc_bounds_for_store_local_days():
    from datetime import date, timezone
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Chicago")
    end = date(2026, 4, 3)
    lo, hi = _mod.utc_bounds_for_store_local_days(tz, end, 3)
    assert lo.tzinfo == timezone.utc
    assert hi.tzinfo == timezone.utc
    assert lo < hi


def test_num_biweek_periods_and_range():
    from datetime import date

    assert _mod.num_biweek_periods(365, 14) == 27
    a, b = _mod.biweek_local_range(date(2026, 1, 1), 0, 14, date(2026, 1, 20))
    assert a == date(2026, 1, 1) and b == date(2026, 1, 14)


def test_parse_brand_exclusions_empty():
    assert _mod.parse_brand_exclusions("") == frozenset()


def test_parse_brand_exclusions_casefold():
    s = "Puffin Pure, (no brand) , Acme"
    assert _mod.parse_brand_exclusions(s) == frozenset({"puffin pure", "(no brand)", "acme"})


def test_brand_excluded():
    ex = frozenset({"(no brand)", "puffin pure"})
    assert _mod.brand_excluded("(no brand)", ex)
    assert _mod.brand_excluded("Puffin Pure", ex)
    assert not _mod.brand_excluded("Cartel", ex)


def test_default_exclude_includes_consignment_casefold():
    ex = _mod.parse_brand_exclusions(_mod.DEFAULT_EXCLUDE_BRANDS)
    assert _mod.brand_excluded("ARCTIC EXTRACTS", ex)
    assert _mod.brand_excluded("Deadhead Farms", ex)
    assert _mod.brand_excluded("Rooted Right Farms", ex)
    assert _mod.brand_excluded("Doc Ferguson", ex)


def test_implied_monthly_cog_throughput_usd():
    # 10 units, $50 COG over ~30.44 day month-equivalent in 365d window → aum and acu positive
    t = _mod.implied_monthly_cog_throughput_usd(100, 10_000, 365)
    assert t is not None and t > 0


def test_cash_cycle_and_cover_status():
    from lib.projection_layer2_recovery import cash_cycle_status_from_recovery_days, cover_status_from_days_of_cover

    assert cash_cycle_status_from_recovery_days(10.0) == "SAFE"
    assert cash_cycle_status_from_recovery_days(14.0) == "SAFE"
    assert cash_cycle_status_from_recovery_days(18.0) == "WARNING"
    assert cash_cycle_status_from_recovery_days(22.0) == "CAPITAL RISK"

    assert cover_status_from_days_of_cover(5.0) == "URGENT"
    assert cover_status_from_days_of_cover(10.0) == "THIN"
    assert cover_status_from_days_of_cover(14.0) == "HEALTHY"
    assert cover_status_from_days_of_cover(25.0) == "HEAVY"


def test_layer2_row_buy_plan_cash_and_demand():
    from lib.projection_layer2_recovery import layer2_row_buy_plan

    # 7-day window, 70 units → 70 u/wk, 10 u/day; COG $1/unit; 14d cap → max_cog $140
    m = layer2_row_buy_plan(
        allocated_cog_usd=100.0,
        recent_units_sold=70,
        recent_gross_cents=140_00,
        recent_cog_cents=70_00,
        velocity_span_inclusive_days=7,
        planner_score=0.5,
        cash_cycle_days=14.0,
    )
    assert m["avg_units_per_week"] == 70.0
    assert m["avg_units_per_day"] is not None and abs(m["avg_units_per_day"] - 10.0) < 1e-6
    assert m["units_needed_14d"] == 140.0
    assert m["max_cog_allowed_usd"] is not None and abs(m["max_cog_allowed_usd"] - 140.0) < 1e-6
    assert m["cash_recovery_days"] is not None and abs(m["cash_recovery_days"] - 10.0) < 1e-6
    assert m["cash_cycle_status"] == "SAFE"


def test_allocate_for_mode_three_modes_sum_to_pool():
    keys = [("Edibles", "A"), ("Cartridges", "B")]
    pair_gross = {keys[0]: 1_000_00, keys[1]: 3_000_00}
    pair_units = {keys[0]: 10, keys[1]: 30}
    pair_cog = {keys[0]: 400_00, keys[1]: 1_200_00}
    pair_ur = {keys[0]: 5, keys[1]: 15}
    pair_gr = {keys[0]: 500_00, keys[1]: 1_500_00}
    pair_cr = {keys[0]: 200_00, keys[1]: 600_00}
    pool = 1800_00
    total_fmt = pair_gross[keys[0]] + pair_gross[keys[1]]
    for mode in ("buy-plan", "throughput", "gross-share"):
        pp, _ps = _mod.allocate_for_mode(
            mode,
            pool,
            keys,
            pair_gross,
            pair_units,
            pair_cog,
            365,
            total_fmt,
            pair_ur,
            pair_gr,
            pair_cr,
            49,
            min_units_per_week=0.01,
            buy_plan_max_rows=10,
            min_allocated_cents=0,
            pool_top_n=15,
            cash_cycle_days=14.0,
        )
        s = sum(pp.values())
        if mode == "buy-plan":
            assert 0 <= s <= pool
        else:
            assert s == pool


def test_allocate_pool_top_n_by_recovery_throughput():
    keys = [("Edibles", "A"), ("Cartridges", "B"), ("Edibles", "C")]
    pair_gross = {keys[0]: 1000, keys[1]: 5000, keys[2]: 2000}
    pair_units = {keys[0]: 10, keys[1]: 100, keys[2]: 5}
    pair_cog = {keys[0]: 500, keys[1]: 4000, keys[2]: 250}
    span = 365
    out = _mod.allocate_pool_top_n_by_recovery_throughput(
        2, 10_000_00, keys, pair_gross, pair_units, pair_cog, span
    )
    assert sum(out.values()) == 10_000_00
    assert out[keys[0]] + out[keys[1]] + out[keys[2]] == 10_000_00
    funded = [k for k, v in out.items() if v > 0]
    assert len(funded) <= 2
    assert all(out[k] == 0 for k in keys if k not in funded)


def test_fetch_chunk_falls_back_when_package_field_is_missing(monkeypatch):
    calls = []

    def fake_fetch_paginated(root, query, variables, *, credentials_path=None):
        calls.append(query)
        if query == _mod.ORDER_ITEMS_QUERY:
            raise RuntimeError("Cannot query field 'Package' on type 'OrderItems'")
        assert query == _mod.ORDER_ITEMS_QUERY_NO_PACKAGE
        return []

    monkeypatch.setattr(_mod, "fetch_paginated", fake_fetch_paginated)

    raw, query = _mod._fetch_chunk(
        oi_query=_mod.ORDER_ITEMS_QUERY,
        where={"SoldAt": {"greaterThanOrEqualTo": "2026-01-01T00:00:00Z"}},
        creds=None,
        chunk_idx=1,
        retries=1,
    )

    assert raw == []
    assert query == _mod.ORDER_ITEMS_QUERY_NO_PACKAGE
    assert calls == [_mod.ORDER_ITEMS_QUERY, _mod.ORDER_ITEMS_QUERY_NO_PACKAGE]


def test_projection_main_dedupes_duplicate_order_items(monkeypatch, tmp_path):
    sold_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    node = {
        "id": "order-line-1",
        "objectId": "order-line-1",
        "SoldAt": sold_at,
        "GrossPrice": 10_000,
        "NetPrice": 10_000,
        "COG": 5_000,
        "ProductCategory": {"Name": "Edibles"},
        "Product": {
            "objectId": "product-1",
            "Name": "Gummy 10pk",
            "Brand": {"Name": "Brand A"},
        },
    }

    def fake_fetch_chunk(**kwargs):
        return [dict(node), dict(node)], kwargs["oi_query"]

    out = tmp_path / "projection.md"
    monkeypatch.setattr(_mod, "_fetch_chunk", fake_fetch_chunk)
    monkeypatch.setattr(_mod, "_load_config_flags", lambda: None)
    monkeypatch.setattr(_mod, "_credentials_path", lambda: None)
    monkeypatch.setattr(_mod, "_store_tz", lambda: timezone.utc)
    monkeypatch.setattr(_mod, "validate_and_normalize", lambda **kwargs: {"ok": True, "report_path": "unit-test"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_projection_by_category_brand.py",
            "--days",
            "1",
            "--chunk-days",
            "1",
            "--allocation-mode",
            "gross-share",
            "--pool-top-n",
            "0",
            "--pool",
            "100",
            "--no-layer2",
            "--exclude-brands",
            "",
            "--out",
            str(out),
        ],
    )

    assert _mod.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "- **Unique order lines counted:** 1" in text
    assert "- **Sales in focus categories (pool-eligible):** $100.00 gross" in text
