"""
SQLite fact store for GrowFlow retail analytics.

Canonical path: data/growflow_facts.db (gitignored).
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = REPO_ROOT / "data" / "growflow_facts.db"

SCHEMA_VERSION = 1

DDL = """
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  run_id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  watermark_from TEXT,
  watermark_to TEXT,
  lines_upserted INTEGER DEFAULT 0,
  orders_upserted INTEGER DEFAULT 0,
  validation_report_path TEXT,
  ok INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stores (
  object_id TEXT PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  object_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  username TEXT
);

CREATE TABLE IF NOT EXISTS products (
  object_id TEXT PRIMARY KEY,
  name TEXT,
  sku TEXT,
  brand_id TEXT,
  category_id TEXT,
  sales_price_cents INTEGER
);

CREATE TABLE IF NOT EXISTS orders (
  object_id TEXT PRIMARY KEY,
  completed_at TEXT,
  total_cents INTEGER,
  subtotal_cents INTEGER,
  discounts_cents INTEGER,
  order_type TEXT,
  status TEXT,
  pre_order_type TEXT,
  budtender_user_id TEXT,
  store_object_id TEXT,
  has_discount INTEGER NOT NULL DEFAULT 0,
  is_return INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS order_lines (
  object_id TEXT PRIMARY KEY,
  sold_at TEXT NOT NULL,
  sold_date_local TEXT NOT NULL,
  order_object_id TEXT,
  store_object_id TEXT,
  budtender_user_id TEXT,
  budtender_name TEXT,
  gross_price_cents INTEGER NOT NULL,
  net_price_cents INTEGER NOT NULL,
  cog_cents INTEGER,
  original_price_cents INTEGER,
  price_cents INTEGER,
  tax_cents INTEGER,
  collected_otd_cents INTEGER,
  discount_cents INTEGER,
  is_return INTEGER NOT NULL DEFAULT 0,
  channel TEXT,
  product_object_id TEXT,
  brand_raw TEXT,
  brand_canonical TEXT,
  category_raw TEXT,
  category_canonical TEXT,
  package_object_id TEXT,
  landed_cost_cents INTEGER,
  ingest_run_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ol_sold_date ON order_lines(sold_date_local);
CREATE INDEX IF NOT EXISTS idx_ol_order ON order_lines(order_object_id);
CREATE INDEX IF NOT EXISTS idx_ol_budtender ON order_lines(budtender_user_id);
CREATE INDEX IF NOT EXISTS idx_ol_brand ON order_lines(brand_canonical);
CREATE INDEX IF NOT EXISTS idx_ol_store ON order_lines(store_object_id);
"""


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    # SaaS-ready seam: default single-org id (override via GROWFLOW_ORG_ID)
    import os

    org_id = (os.environ.get("GROWFLOW_ORG_ID") or "nugz").strip() or "nugz"
    conn.execute(
        "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
        ("org_id", org_id),
    )
    conn.commit()


def get_org_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM schema_meta WHERE key='org_id'").fetchone()
    return str(row["value"]) if row else "nugz"


def upsert_store(conn: sqlite3.Connection, object_id: str, name: str) -> None:
    conn.execute(
        "INSERT INTO stores(object_id, name) VALUES (?, ?) ON CONFLICT(object_id) DO UPDATE SET name=excluded.name",
        (object_id, name),
    )


def upsert_user(conn: sqlite3.Connection, object_id: str, display_name: str, username: str | None) -> None:
    conn.execute(
        """INSERT INTO users(object_id, display_name, username) VALUES (?, ?, ?)
           ON CONFLICT(object_id) DO UPDATE SET display_name=excluded.display_name, username=excluded.username""",
        (object_id, display_name, username),
    )


def upsert_product(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO products(object_id, name, sku, brand_id, category_id, sales_price_cents)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(object_id) DO UPDATE SET
             name=excluded.name, sku=excluded.sku, brand_id=excluded.brand_id,
             category_id=excluded.category_id, sales_price_cents=excluded.sales_price_cents""",
        (
            row["object_id"],
            row.get("name"),
            row.get("sku"),
            row.get("brand_id"),
            row.get("category_id"),
            row.get("sales_price_cents"),
        ),
    )


def upsert_order(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO orders(
             object_id, completed_at, total_cents, subtotal_cents, discounts_cents,
             order_type, status, pre_order_type, budtender_user_id, store_object_id,
             has_discount, is_return
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(object_id) DO UPDATE SET
             completed_at=excluded.completed_at, total_cents=excluded.total_cents,
             subtotal_cents=excluded.subtotal_cents, discounts_cents=excluded.discounts_cents,
             order_type=excluded.order_type, status=excluded.status,
             pre_order_type=excluded.pre_order_type, budtender_user_id=excluded.budtender_user_id,
             store_object_id=excluded.store_object_id, has_discount=excluded.has_discount,
             is_return=excluded.is_return""",
        (
            row["object_id"],
            row.get("completed_at"),
            row.get("total_cents"),
            row.get("subtotal_cents"),
            row.get("discounts_cents"),
            row.get("order_type"),
            row.get("status"),
            row.get("pre_order_type"),
            row.get("budtender_user_id"),
            row.get("store_object_id"),
            row.get("has_discount", 0),
            row.get("is_return", 0),
        ),
    )


def upsert_order_line(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = [
        "object_id", "sold_at", "sold_date_local", "order_object_id", "store_object_id",
        "budtender_user_id", "budtender_name", "gross_price_cents", "net_price_cents",
        "cog_cents", "original_price_cents", "price_cents", "tax_cents", "collected_otd_cents",
        "discount_cents", "is_return", "channel", "product_object_id", "brand_raw",
        "brand_canonical", "category_raw", "category_canonical", "package_object_id",
        "landed_cost_cents", "ingest_run_id",
    ]
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "object_id")
    values = tuple(row.get(c) for c in cols)
    conn.execute(
        f"""INSERT INTO order_lines({", ".join(cols)}) VALUES ({placeholders})
            ON CONFLICT(object_id) DO UPDATE SET {updates}""",
        values,
    )


def start_ingest_run(conn: sqlite3.Connection, run_id: str, watermark_from: str | None, watermark_to: str | None) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    conn.execute(
        """INSERT INTO ingest_runs(run_id, started_at, watermark_from, watermark_to, ok)
           VALUES (?, ?, ?, ?, 0)""",
        (run_id, now, watermark_from, watermark_to),
    )
    conn.commit()


def finish_ingest_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    lines_upserted: int,
    orders_upserted: int,
    validation_report_path: str | None,
    ok: bool,
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    conn.execute(
        """UPDATE ingest_runs SET finished_at=?, lines_upserted=?, orders_upserted=?,
           validation_report_path=?, ok=? WHERE run_id=?""",
        (now, lines_upserted, orders_upserted, validation_report_path, 1 if ok else 0, run_id),
    )
    conn.commit()


def max_sold_at(conn: sqlite3.Connection) -> str | None:
    row = conn.execute("SELECT MAX(sold_at) AS m FROM order_lines").fetchone()
    return str(row["m"]) if row and row["m"] else None


def query_lines_between(
    conn: sqlite3.Connection,
    start_local: str,
    end_local: str,
    *,
    store_object_id: str | None = None,
    channel: str | None = None,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM order_lines WHERE sold_date_local >= ? AND sold_date_local <= ?"
    params: list[Any] = [start_local, end_local]
    if store_object_id:
        sql += " AND store_object_id = ?"
        params.append(store_object_id)
    if channel and channel not in ("all", ""):
        sql += " AND channel = ?"
        params.append(channel)
    sql += " ORDER BY sold_at"
    return list(conn.execute(sql, params).fetchall())
