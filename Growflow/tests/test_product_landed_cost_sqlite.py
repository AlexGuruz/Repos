"""Tests for ``lib/product_landed_cost_sqlite`` materialization."""

from __future__ import annotations

import sqlite3

from lib.product_landed_cost_sqlite import (
    dashboard_notes_transfer_cost_rows,
    rebuild_product_landed_cost_current,
)


def _minimal_receipt_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE transfer_receipts (
            transfer_object_id TEXT PRIMARY KEY,
            transfer_status TEXT,
            received_at TEXT,
            transfer_created_at TEXT,
            transfer_updated_at TEXT,
            from_name TEXT,
            store_object_id TEXT,
            store_name TEXT,
            receiving_store_object_id TEXT,
            receiving_store_name TEXT,
            loaded_at TEXT NOT NULL
        );
        CREATE TABLE transfer_receipt_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_object_id TEXT NOT NULL,
            package_object_id TEXT,
            package_sku TEXT,
            original_qty INTEGER NOT NULL,
            current_qty INTEGER NOT NULL,
            cost_cents INTEGER NOT NULL,
            product_object_id TEXT,
            product_name TEXT,
            product_sku TEXT,
            brand_name TEXT,
            received_at TEXT,
            received_date_local TEXT,
            sales_timezone TEXT,
            loaded_at TEXT NOT NULL
        );
        """
    )


def test_rebuild_picks_latest_receipt_per_product() -> None:
    conn = sqlite3.connect(":memory:")
    _minimal_receipt_schema(conn)
    conn.executemany(
        """
        INSERT INTO transfer_receipts (
            transfer_object_id, transfer_status, received_at, from_name,
            receiving_store_object_id, receiving_store_name, loaded_at
        ) VALUES (?, 'Accepted', ?, 'Supplier A', 'store1', 'Store 1', 'Z')
        """,
        [
            ("t_old", "2025-06-01T12:00:00.000Z"),
            ("t_new", "2026-01-15T12:00:00.000Z"),
        ],
    )
    conn.execute(
        """
        INSERT INTO transfer_receipt_packages (
            transfer_object_id, package_object_id, package_sku, original_qty, current_qty,
            cost_cents, product_object_id, product_name, product_sku, brand_name,
            received_at, received_date_local, sales_timezone, loaded_at
        ) VALUES
        ('t_old', 'pkg1', 'SKU-1', 10, 10, 35000, 'prod1', 'Geek Bar', 'GB-1', 'Geek',
         '2025-06-01T12:00:00.000Z', '2025-06-01', 'America/Denver', 'Z'),
        ('t_new', 'pkg2', 'SKU-1', 10, 10, 40000, 'prod1', 'Geek Bar', 'GB-1', 'Geek',
         '2026-01-15T12:00:00.000Z', '2026-01-15', 'America/Denver', 'Z')
        """
    )
    n = rebuild_product_landed_cost_current(conn)
    assert n == 1
    row = conn.execute(
        "SELECT transfer_object_id, line_cost_cents, unit_cost_usd FROM product_landed_cost_current"
    ).fetchone()
    assert row is not None
    assert row[0] == "t_new"
    assert row[1] == 40000
    assert abs(row[2] - 40.0) < 1e-9
    conn.close()


def test_skips_null_product_and_zero_qty() -> None:
    conn = sqlite3.connect(":memory:")
    _minimal_receipt_schema(conn)
    conn.execute(
        """
        INSERT INTO transfer_receipts (
            transfer_object_id, transfer_status, received_at, from_name,
            receiving_store_object_id, receiving_store_name, loaded_at
        ) VALUES ('t1', 'Accepted', '2026-01-01T00:00:00.000Z', 'S', NULL, NULL, 'Z')
        """
    )
    conn.execute(
        """
        INSERT INTO transfer_receipt_packages (
            transfer_object_id, package_object_id, package_sku, original_qty, current_qty,
            cost_cents, product_object_id, product_name, product_sku, brand_name,
            received_at, received_date_local, sales_timezone, loaded_at
        ) VALUES
        ('t1', 'p1', 'X', 0, 0, 1000, 'prodZ', 'Z', 'z', 'B',
         '2026-01-01T00:00:00.000Z', '2026-01-01', 'UTC', 'Z'),
        ('t1', 'p2', 'Y', 5, 5, 2500, '', 'No id', 'y', 'B',
         '2026-01-01T00:00:00.000Z', '2026-01-01', 'UTC', 'Z')
        """
    )
    n = rebuild_product_landed_cost_current(conn)
    assert n == 0
    conn.close()


def test_dashboard_notes_when_no_sidecar_csv(tmp_path) -> None:
    layer2 = tmp_path / "projection_by_category_brand_layer2_recovery.csv"
    layer2.write_text("h\n")
    rows = dashboard_notes_transfer_cost_rows(layer2)
    assert len(rows) == 1
    assert rows[0][0] == "Transfer receipts → landed COG (optional)"
    assert "No product_landed_cost_current.csv" in rows[0][1]


def test_dashboard_notes_when_csv_beside_layer2(tmp_path) -> None:
    layer2 = tmp_path / "layer2.csv"
    layer2.write_text("h\n")
    side = tmp_path / "product_landed_cost_current.csv"
    side.write_text("product_object_id,unit_cost_usd\nx,1\n")
    rows = dashboard_notes_transfer_cost_rows(layer2)
    assert len(rows) == 1
    assert "Found" in rows[0][1]
    assert "Not auto-merged" in rows[0][1]
