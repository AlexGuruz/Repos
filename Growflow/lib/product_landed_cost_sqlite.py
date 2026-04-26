"""
Latest **landed package cost per product** from Growflow transfer receipts already loaded into SQLite.

``transfer_receipt_packages`` / ``transfer_receipts`` are populated by
``scripts/build_transfer_receipts_db.py`` from ``findTransfers`` package lines
(``Packages.Cost`` in cents, ``OriginalQty``, ``Product.objectId``).

This module **refines** raw rows into ``product_landed_cost_current``:
one row per ``product_object_id`` = the most recent receipt line by ``received_at``
(then transfer / package / row id as tie-breakers).

**Interpretation:** ``Cost`` is treated as **line total cents** for the package line;
``unit_cost_usd`` = ``(cost_cents / 100) / original_qty``. If your org stores Cost
differently, adjust downstream consumers or add a config flag later.

**Dashboard / Sheets alignment (important):**

- The capital dashboard (``scripts/build_projection_dashboard_google_sheet.py``) pushes
  **``raw_layer2`` / ``dashboard_data`` from the layer2 CSV** only
  (``projection_by_category_brand_layer2_recovery.csv`` from
  ``build_projection_by_category_brand.py``). Formulas reference **brand × category**
  columns on that CSV, not this SQLite file.
- ``product_landed_cost_current`` is **SKU / Product.objectId grain** (Growflow
  transfer truth). It does **not** automatically change dashboard numbers until the
  projection pipeline joins ``Product.objectId`` (or you import the optional CSV
  beside the layer2 file for side-by-side review).
- **Convention:** export CSV as ``data/product_landed_cost_current.csv`` or place it
  next to the layer2 CSV so the Notes tab can point operators to the same folder.

See also: ``DEFAULT_PRODUCT_LANDED_COST_CSV``.
"""
from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Conventional export path (repo ``data/``); used by docs and dashboard Notes hints.
DEFAULT_PRODUCT_LANDED_COST_CSV = Path(__file__).resolve().parents[1] / "data" / "product_landed_cost_current.csv"


def ensure_product_landed_cost_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS product_landed_cost_current (
            product_object_id TEXT PRIMARY KEY,
            brand_name TEXT,
            product_name TEXT,
            product_sku TEXT,
            package_sku TEXT,
            transfer_object_id TEXT NOT NULL,
            package_object_id TEXT,
            received_at TEXT NOT NULL,
            received_date_local TEXT,
            original_qty INTEGER NOT NULL,
            line_cost_cents INTEGER NOT NULL,
            unit_cost_cents REAL,
            unit_cost_usd REAL,
            from_name TEXT,
            receiving_store_object_id TEXT,
            receiving_store_name TEXT,
            derived_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_plcc_brand ON product_landed_cost_current(brand_name);
        CREATE INDEX IF NOT EXISTS idx_plcc_received ON product_landed_cost_current(received_at);
        """
    )


def rebuild_product_landed_cost_current(conn: sqlite3.Connection) -> int:
    """
    Replace ``product_landed_cost_current`` from all rows in ``transfer_receipt_packages``.

    Returns number of product rows written.
    """
    ensure_product_landed_cost_schema(conn)
    derived_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    conn.execute("DELETE FROM product_landed_cost_current")
    conn.execute(
        """
        INSERT INTO product_landed_cost_current (
            product_object_id, brand_name, product_name, product_sku, package_sku,
            transfer_object_id, package_object_id, received_at, received_date_local,
            original_qty, line_cost_cents, unit_cost_cents, unit_cost_usd,
            from_name, receiving_store_object_id, receiving_store_name, derived_at
        )
        SELECT
            r.product_object_id,
            r.brand_name,
            r.product_name,
            r.product_sku,
            r.package_sku,
            r.transfer_object_id,
            r.package_object_id,
            r.received_at,
            r.received_date_local,
            r.original_qty,
            r.cost_cents,
            CASE
                WHEN r.original_qty > 0 THEN CAST(r.cost_cents AS REAL) / r.original_qty
                ELSE NULL
            END,
            CASE
                WHEN r.original_qty > 0 THEN (CAST(r.cost_cents AS REAL) / 100.0) / r.original_qty
                ELSE NULL
            END,
            t.from_name,
            t.receiving_store_object_id,
            t.receiving_store_name,
            ?
        FROM (
            SELECT
                p.*,
                ROW_NUMBER() OVER (
                    PARTITION BY p.product_object_id
                    ORDER BY
                        p.received_at DESC,
                        p.transfer_object_id DESC,
                        IFNULL(p.package_object_id, '') DESC,
                        p.id DESC
                ) AS rn
            FROM transfer_receipt_packages p
            WHERE p.product_object_id IS NOT NULL
              AND TRIM(p.product_object_id) != ''
              AND p.original_qty > 0
              AND p.cost_cents >= 0
        ) r
        LEFT JOIN transfer_receipts t ON t.transfer_object_id = r.transfer_object_id
        WHERE r.rn = 1
        """,
        (derived_at,),
    )
    cur = conn.execute("SELECT COUNT(*) FROM product_landed_cost_current")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def dashboard_notes_transfer_cost_rows(layer2_csv_path: Path) -> list[list[str]]:
    """
    Two-column note rows for the capital dashboard **Notes** tab.

    Clarifies that Sheets ``raw_layer2`` / formulas follow the **layer2 CSV** (brand×category)
    while ``product_landed_cost_current`` is optional **SKU-level** transfer truth.
    """
    beside = layer2_csv_path.parent / "product_landed_cost_current.csv"
    found = (
        beside
        if beside.is_file()
        else (DEFAULT_PRODUCT_LANDED_COST_CSV if DEFAULT_PRODUCT_LANDED_COST_CSV.is_file() else None)
    )
    gen_cmd = (
        "PYTHONPATH=. python scripts/build_transfer_receipts_db.py --since <ISO_Z> "
        f'--export-product-costs-csv "{DEFAULT_PRODUCT_LANDED_COST_CSV.as_posix()}"'
    )
    if found is not None:
        msg = (
            f"Found {found.resolve().as_posix()} — latest Growflow transfer package cost per "
            "Product.objectId. **Not auto-merged** into raw_layer2 or dashboard_data; numbers on "
            "this workbook still come only from the layer2 CSV (trailing order-line economics / "
            "buy-plan allocator at brand×category grain). Use this file for IMPORTRANGE, BI joins, "
            "or wire build_projection_by_category_brand.py to blend transfer unit COG before export."
        )
    else:
        msg = (
            "No product_landed_cost_current.csv beside this CSV and none at "
            f"{DEFAULT_PRODUCT_LANDED_COST_CSV.as_posix()}. To publish landed costs for review: "
            f"{gen_cmd}"
        )
    return [["Transfer receipts → landed COG (optional)", msg]]


def export_product_landed_cost_current_csv(conn: sqlite3.Connection, path: Path) -> int:
    """Write ``product_landed_cost_current`` to CSV; returns row count."""
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = conn.execute(
        "SELECT * FROM product_landed_cost_current ORDER BY brand_name, product_name"
    )
    cols = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


