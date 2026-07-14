"""Persist dashboard payloads to retail_dashboard.db."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.retail_dashboard.metrics import DashboardPayload

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_PATH = REPO_ROOT / "data" / "retail_dashboard.db"

CACHE_DDL = """
CREATE TABLE IF NOT EXISTS dashboard_runs (
  run_id TEXT PRIMARY KEY,
  built_at TEXT NOT NULL,
  period_start TEXT,
  period_end TEXT,
  prior_start TEXT,
  prior_end TEXT,
  store_id TEXT,
  channel TEXT,
  validation_ok INTEGER,
  meta_json TEXT
);

CREATE TABLE IF NOT EXISTS budtender_sales (
  run_id TEXT NOT NULL,
  budtender_name TEXT NOT NULL,
  net_sales REAL,
  order_count INTEGER,
  aov REAL,
  effective_discount_pct REAL,
  pct_orders_discounted REAL,
  pct_net_sales REAL,
  flags_json TEXT,
  PRIMARY KEY (run_id, budtender_name)
);

CREATE TABLE IF NOT EXISTS discounts_daily (
  run_id TEXT NOT NULL,
  date_local TEXT NOT NULL,
  net_sales REAL,
  effective_discount_pct REAL,
  pct_orders_discounted REAL,
  PRIMARY KEY (run_id, date_local)
);

CREATE TABLE IF NOT EXISTS budtender_category (
  run_id TEXT NOT NULL,
  category_name TEXT NOT NULL,
  budtender_name TEXT NOT NULL,
  gross_sales REAL,
  net_sales REAL,
  item_count INTEGER,
  PRIMARY KEY (run_id, category_name, budtender_name)
);

CREATE TABLE IF NOT EXISTS brand_summary (
  run_id TEXT NOT NULL,
  brand_canonical TEXT NOT NULL,
  brand_name TEXT,
  net_sales REAL,
  returns_pct REAL,
  effective_discount_pct REAL,
  native_margin_pct REAL,
  landed_margin_pct REAL,
  cog_vs_landed_delta_pct REAL,
  profit_velocity_rank INTEGER,
  PRIMARY KEY (run_id, brand_canonical)
);

CREATE TABLE IF NOT EXISTS period_compare_kpis (
  run_id TEXT NOT NULL,
  metric_key TEXT NOT NULL,
  current_value REAL,
  prior_value REAL,
  delta_abs REAL,
  delta_pct REAL,
  PRIMARY KEY (run_id, metric_key)
);

CREATE TABLE IF NOT EXISTS alerts (
  run_id TEXT NOT NULL,
  alert_id TEXT NOT NULL,
  severity TEXT,
  code TEXT,
  message TEXT,
  payload_json TEXT,
  PRIMARY KEY (run_id, alert_id)
);
"""


def connect_cache(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else DEFAULT_CACHE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.executescript(CACHE_DDL)
    return conn


def save_payload(conn: sqlite3.Connection, run_id: str, payload: DashboardPayload, *, validation_ok: bool) -> None:
    built = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = payload.meta
    period = meta.get("period") or {}
    prior = meta.get("prior_period") or {}

    conn.execute("DELETE FROM budtender_sales WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM discounts_daily WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM budtender_category WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM brand_summary WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM period_compare_kpis WHERE run_id=?", (run_id,))
    conn.execute("DELETE FROM alerts WHERE run_id=?", (run_id,))

    conn.execute(
        """INSERT OR REPLACE INTO dashboard_runs(
             run_id, built_at, period_start, period_end, prior_start, prior_end,
             store_id, channel, validation_ok, meta_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            built,
            period.get("start"),
            period.get("end"),
            prior.get("start") if prior else None,
            prior.get("end") if prior else None,
            meta.get("store_id"),
            meta.get("channel"),
            1 if validation_ok else 0,
            json.dumps(meta, ensure_ascii=False),
        ),
    )

    for row in payload.budtender_sales:
        conn.execute(
            """INSERT INTO budtender_sales(
                 run_id, budtender_name, net_sales, order_count, aov,
                 effective_discount_pct, pct_orders_discounted, pct_net_sales, flags_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                row["budtender"],
                row["net_sales"],
                row["order_count"],
                row["aov"],
                row["effective_discount_pct"],
                row["pct_orders_discounted"],
                row["pct_net_sales"],
                json.dumps(row.get("flags") or []),
            ),
        )

    for row in payload.discounts_over_time:
        conn.execute(
            """INSERT INTO discounts_daily(
                 run_id, date_local, net_sales, effective_discount_pct, pct_orders_discounted
               ) VALUES (?, ?, ?, ?, ?)""",
            (
                run_id,
                row["date"],
                row["net_sales"],
                row["effective_discount_pct"],
                row["pct_orders_discounted"],
            ),
        )

    for row in payload.budtender_by_category:
        conn.execute(
            """INSERT INTO budtender_category(
                 run_id, category_name, budtender_name, gross_sales, net_sales, item_count
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                row["category_name"],
                row["budtender"],
                row["gross_sales"],
                row["net_sales"],
                row["item_count"],
            ),
        )

    for row in payload.brand_summary:
        conn.execute(
            """INSERT INTO brand_summary(
                 run_id, brand_canonical, brand_name, net_sales, returns_pct,
                 effective_discount_pct, native_margin_pct, landed_margin_pct,
                 cog_vs_landed_delta_pct, profit_velocity_rank
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                row["canonical_brand"],
                row["brand_name"],
                row["net_sales"],
                row["returns_pct"],
                row["effective_discount_pct"],
                row.get("native_margin_pct"),
                row.get("landed_margin_pct"),
                row.get("cog_vs_landed_delta_pct"),
                row.get("profit_velocity_rank"),
            ),
        )

    for row in payload.period_compare_kpis:
        conn.execute(
            """INSERT INTO period_compare_kpis(
                 run_id, metric_key, current_value, prior_value, delta_abs, delta_pct
               ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                row["key"],
                row.get("current"),
                row.get("prior"),
                row.get("delta_abs"),
                row.get("delta_pct"),
            ),
        )

    for row in payload.alerts:
        conn.execute(
            """INSERT INTO alerts(run_id, alert_id, severity, code, message, payload_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                row["alert_id"],
                row.get("severity"),
                row.get("code"),
                row.get("message"),
                json.dumps(row, ensure_ascii=False),
            ),
        )
    conn.commit()


def load_latest(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT run_id FROM dashboard_runs ORDER BY built_at DESC LIMIT 1"
    ).fetchone()
    if not row:
        return None
    return load_run(conn, str(row["run_id"]))


def load_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    run = conn.execute("SELECT * FROM dashboard_runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        return None
    meta = json.loads(run["meta_json"] or "{}")
    return {
        "meta": {
            **meta,
            "run_id": run_id,
            "built_at": run["built_at"],
            "validation": {"ok": bool(run["validation_ok"])},
        },
        "period_compare_kpis": [
            dict(r)
            for r in conn.execute(
                "SELECT metric_key AS key, current_value AS current, prior_value AS prior, "
                "delta_abs, delta_pct FROM period_compare_kpis WHERE run_id=?",
                (run_id,),
            )
        ],
        "budtender_sales": [
            {
                **dict(r),
                "budtender": r["budtender_name"],
                "flags": json.loads(r["flags_json"] or "[]"),
            }
            for r in conn.execute("SELECT * FROM budtender_sales WHERE run_id=? ORDER BY net_sales DESC", (run_id,))
        ],
        "discounts_over_time": [
            {
                "date": r["date_local"],
                "net_sales": r["net_sales"],
                "effective_discount_pct": r["effective_discount_pct"],
                "pct_orders_discounted": r["pct_orders_discounted"],
            }
            for r in conn.execute("SELECT * FROM discounts_daily WHERE run_id=? ORDER BY date_local", (run_id,))
        ],
        "budtender_by_category": [
            {
                "category_name": r["category_name"],
                "budtender": r["budtender_name"],
                "gross_sales": r["gross_sales"],
                "net_sales": r["net_sales"],
                "item_count": r["item_count"],
            }
            for r in conn.execute(
                "SELECT * FROM budtender_category WHERE run_id=? ORDER BY category_name, net_sales DESC",
                (run_id,),
            )
        ],
        "brand_summary": [
            {
                "brand_name": r["brand_name"],
                "canonical_brand": r["brand_canonical"],
                "net_sales": r["net_sales"],
                "returns_pct": r["returns_pct"],
                "effective_discount_pct": r["effective_discount_pct"],
                "native_margin_pct": r["native_margin_pct"],
                "landed_margin_pct": r["landed_margin_pct"],
                "cog_vs_landed_delta_pct": r["cog_vs_landed_delta_pct"],
                "profit_velocity_rank": r["profit_velocity_rank"],
            }
            for r in conn.execute("SELECT * FROM brand_summary WHERE run_id=? ORDER BY net_sales DESC", (run_id,))
        ],
        "alerts": [
            {
                "alert_id": r["alert_id"],
                "severity": r["severity"],
                "code": r["code"],
                "message": r["message"],
            }
            for r in conn.execute("SELECT * FROM alerts WHERE run_id=?", (run_id,))
        ],
    }
