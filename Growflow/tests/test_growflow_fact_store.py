"""Tests for growflow_facts.db fact store."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from lib.growflow_fact_store import (
    connect,
    init_db,
    query_lines_between,
    upsert_order_line,
    upsert_store,
    upsert_user,
)


def test_init_and_upsert_line(tmp_path: Path):
    db = tmp_path / "facts.db"
    conn = connect(db)
    init_db(conn)
    upsert_store(conn, "store1", "Test Store")
    upsert_user(conn, "u1", "Alice Budtender", "alice")
    upsert_order_line(
        conn,
        {
            "object_id": "line1",
            "sold_at": "2026-06-01T15:00:00.000Z",
            "sold_date_local": "2026-06-01",
            "order_object_id": "ord1",
            "store_object_id": "store1",
            "budtender_user_id": "u1",
            "budtender_name": "Alice Budtender",
            "gross_price_cents": 2000,
            "net_price_cents": 1800,
            "cog_cents": 800,
            "original_price_cents": 2000,
            "price_cents": 1800,
            "tax_cents": 200,
            "collected_otd_cents": 1800,
            "discount_cents": 200,
            "is_return": 0,
            "channel": "in_store",
            "product_object_id": "p1",
            "brand_raw": "BrandA",
            "brand_canonical": "BrandA",
            "category_raw": "Flower",
            "category_canonical": "Flower",
            "package_object_id": None,
            "landed_cost_cents": 900,
            "ingest_run_id": "run_test",
        },
    )
    conn.commit()
    rows = query_lines_between(conn, "2026-06-01", "2026-06-01")
    assert len(rows) == 1
    assert rows[0]["budtender_name"] == "Alice Budtender"
    assert rows[0]["net_price_cents"] == 1800
    conn.close()


def test_store_filter(tmp_path: Path):
    db = tmp_path / "facts.db"
    conn = connect(db)
    init_db(conn)
    base = {
        "sold_at": "2026-06-01T15:00:00.000Z",
        "sold_date_local": "2026-06-01",
        "order_object_id": "o1",
        "gross_price_cents": 1000,
        "net_price_cents": 1000,
        "discount_cents": 0,
        "is_return": 0,
        "channel": "in_store",
        "brand_canonical": "B",
        "category_canonical": "C",
        "ingest_run_id": "r",
    }
    upsert_order_line(conn, {**base, "object_id": "l1", "store_object_id": "s1"})
    upsert_order_line(conn, {**base, "object_id": "l2", "store_object_id": "s2"})
    conn.commit()
    rows = query_lines_between(conn, "2026-06-01", "2026-06-01", store_object_id="s1")
    assert len(rows) == 1
    assert rows[0]["object_id"] == "l1"
    conn.close()
