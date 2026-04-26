"""Tests for lib.brand_merit_pool (no API)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from lib.brand_merit_pool import (
    accumulate_order_lines_chunk,
    aggregate_brand_merit_inputs,
    category_matches_format_substrings,
    merit_weights,
    minmax_norm,
    order_line_format_bucket,
    order_line_in_format_product_pool,
    package_format_bucket,
    package_in_format_product_pool,
    product_format_bucket,
    rows_from_order_acc_and_packages,
)


def test_minmax_norm():
    assert minmax_norm([1.0, 3.0]) == [0.0, 1.0]
    assert minmax_norm([5.0, 5.0]) == [1.0, 1.0]


def test_format_product_pool_category_match():
    subs = ("edible", "cartridge", "disposable", "topical", "preroll", "pre-roll", "vape", "vapor")
    assert category_matches_format_substrings("Edibles", subs)
    assert category_matches_format_substrings("Vape Cartridges", subs)
    assert category_matches_format_substrings("Disposable Vape", subs)
    assert category_matches_format_substrings("Vape Pens", subs)
    assert category_matches_format_substrings("Infused Prerolls", subs)
    assert category_matches_format_substrings("Pre-Roll", subs)
    assert category_matches_format_substrings("Topicals", subs)
    assert not category_matches_format_substrings("Flower", subs)
    assert not category_matches_format_substrings("", subs)
    assert not category_matches_format_substrings(None, subs)


def test_product_format_bucket():
    assert product_format_bucket("Infused Prerolls") == "Infused prerolls"
    assert product_format_bucket("Pre-Roll") == "Prerolls"
    assert product_format_bucket("Edibles") == "Edibles"
    assert product_format_bucket("Vape Cartridges") == "Cartridges"
    assert product_format_bucket("Disposable Vape") == "Disposables"
    assert product_format_bucket("Topicals") == "Topicals"
    assert product_format_bucket("Flower") == "Other"
    # Wrong Growflow category but product title proves disposable / cart
    assert product_format_bucket("Concentrates", "Brand 1G AIO Live Resin") == "Disposables"
    assert product_format_bucket("Accessories", "Brand 510 Vape Cart 1G") == "Cartridges"


def test_order_line_format_bucket_uses_product_name():
    line = {
        "ProductCategory": {"Name": "Vape Cartridges"},
        "Product": {"Name": "Cartel LR Disposable 1G", "Brand": {"Name": "Cartel"}},
    }
    assert order_line_format_bucket(line) == "Disposables"


def test_package_format_bucket_uses_product_name():
    pkg = {
        "Product": {
            "Name": "Brand Disposable Vape",
            "SKU": "X",
            "ProductCategory": {"Name": "Cartridges & Disposables"},
        }
    }
    assert package_format_bucket(pkg) == "Disposables"


def test_product_format_bucket_disposable_vs_cartridge_product_name():
    # Category says carts but product is a disposable device (Cartel-style mis-tagged categories).
    assert product_format_bucket("Vape Cartridges", "Cartel LR Disposable 1G") == "Disposables"
    assert product_format_bucket("Cartridges", "Cartel Disposables Live Resin") == "Disposables"
    assert product_format_bucket("Cartridges", None) == "Cartridges"
    # Combined Growflow category: split using Product.Name.
    assert product_format_bucket("Cartridges & Disposables", "Brand 510 Thread Cartridge 1g") == "Cartridges"
    assert product_format_bucket("Cartridges & Disposables", "Brand Disposable Vape 1g") == "Disposables"
    assert product_format_bucket("Non-Disposable Cartridges", "Brand 510") == "Cartridges"
    # Vague "vape" category + AIO in title.
    assert product_format_bucket("Vape Pens", "Brand AIO Live Resin") == "Disposables"
    assert product_format_bucket("Vape Pens", "Brand 510 Cartridge") == "Cartridges"


def test_order_line_and_package_format_pool():
    line = {"ProductCategory": {"Name": "Edibles"}}
    assert order_line_in_format_product_pool(line)
    line2 = {"ProductCategory": {"Name": "Prepackaged Flower"}}
    assert not order_line_in_format_product_pool(line2)
    pkg = {"Product": {"ProductCategory": {"Name": "Cartridge"}, "SKU": "X"}}
    assert package_in_format_product_pool(pkg)
    # Category alone outside substring list, but resolved bucket is Disposables
    line3 = {
        "ProductCategory": {"Name": "Concentrates"},
        "Product": {"Name": "LR 1G AIO", "Brand": {"Name": "X"}},
    }
    assert order_line_format_bucket(line3) == "Disposables"
    assert order_line_in_format_product_pool(line3)
    pkg3 = {
        "Product": {
            "ProductCategory": {"Name": "Misc"},
            "Name": "Disposable Vape Pen 1G",
            "SKU": "Y",
        }
    }
    assert package_format_bucket(pkg3) == "Disposables"
    assert package_in_format_product_pool(pkg3)


def test_aggregate_and_merit_simple():
    tz = ZoneInfo("America/Chicago")
    today = date(2026, 4, 3)
    # Two lines for brand A on recent day, one old for B
    d_recent = datetime(2026, 4, 2, 18, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    d_old = datetime(2025, 6, 1, 18, 0, 0, tzinfo=tz).astimezone(timezone.utc)

    lines = [
        {
            "SoldAt": d_recent.isoformat().replace("+00:00", "Z"),
            "GrossPrice": 10000,
            "COG": 4000,
            "Product": {"Brand": {"Name": "Alpha"}, "SKU": "A1"},
        },
        {
            "SoldAt": d_recent.isoformat().replace("+00:00", "Z"),
            "GrossPrice": 5000,
            "COG": 2000,
            "Product": {"Brand": {"Name": "Alpha"}, "SKU": "A2"},
        },
        {
            "SoldAt": d_old.isoformat().replace("+00:00", "Z"),
            "GrossPrice": 20000,
            "COG": 10000,
            "Product": {"Brand": {"Name": "Beta"}, "SKU": "B1"},
        },
    ]
    pkgs = [
        {
            "CurrentQty": 10,
            "Cost": 1000,
            "SKU": "A1",
            "Product": {"Brand": {"Name": "Alpha"}, "SKU": "A1"},
        },
        {
            "CurrentQty": 100,
            "Cost": 500,
            "SKU": "B1",
            "Product": {"Brand": {"Name": "Beta"}, "SKU": "B1"},
        },
    ]
    agg = aggregate_brand_merit_inputs(
        lines,
        pkgs,
        today_local=today,
        velocity_days=14,
        store_tz=tz,
    )
    assert "Alpha" in agg and "Beta" in agg
    w, issues = merit_weights(sorted(agg.values(), key=lambda r: r.brand))
    assert not issues or "FALLBACK" not in "".join(issues)
    assert abs(sum(w) - 1.0) < 1e-6 or sum(w) > 0
    pool = 1_800_000  # $18k cents
    from lib.allocate_stock_pool import allocate_pool_cents_largest_remainder

    alloc = allocate_pool_cents_largest_remainder(pool, w)
    assert sum(alloc) == pool


def test_incremental_order_acc_matches_aggregate():
    tz = ZoneInfo("America/Chicago")
    today = date(2026, 4, 3)
    d1 = datetime(2026, 4, 2, 18, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    d2 = datetime(2025, 6, 1, 18, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    lines = [
        {
            "SoldAt": d1.isoformat().replace("+00:00", "Z"),
            "GrossPrice": 1000,
            "COG": 400,
            "Product": {"Brand": {"Name": "A"}, "SKU": "s1"},
        },
        {
            "SoldAt": d2.isoformat().replace("+00:00", "Z"),
            "GrossPrice": 2000,
            "COG": 1000,
            "Product": {"Brand": {"Name": "B"}, "SKU": "s2"},
        },
    ]
    full = aggregate_brand_merit_inputs(
        lines, [], today_local=today, velocity_days=14, store_tz=tz, sku_to_brand={}
    )
    acc: dict = {}
    accumulate_order_lines_chunk(lines, acc, today_local=today, velocity_days=14, store_tz=tz)
    inc = rows_from_order_acc_and_packages(acc, [], {})
    assert len(full) == len(inc)
    for b in full:
        assert full[b].gross_year_cents == inc[b].gross_year_cents
        assert full[b].margin_cents == inc[b].margin_cents
