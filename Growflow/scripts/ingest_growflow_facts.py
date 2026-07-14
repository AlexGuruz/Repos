"""
Ingest GrowFlow order lines into growflow_facts.db (canonical fact store).

Usage:
  PYTHONPATH=. python scripts/ingest_growflow_facts.py --days 30
  PYTHONPATH=. python scripts/ingest_growflow_facts.py --days 7 --validation-mode strict
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.allocate_stock_pool import iter_sold_at_date_chunks
from lib.data_validation_gateway import validate_and_normalize
from lib.growflow_config import load_config
from lib.growflow_fact_store import (
    DEFAULT_DB_PATH,
    connect,
    finish_ingest_run,
    init_db,
    start_ingest_run,
    upsert_order,
    upsert_order_line,
    upsert_product,
    upsert_store,
    upsert_user,
)
from lib.growflow_queries import PAGE_SIZE, date_range_to_where, fetch_order_items_retail_dashboard, fetch_products_catalog, fetch_stores
from lib.retail_dashboard.normalize import (
    extract_store,
    first_order_fragment,
    normalize_order_line,
    normalize_product,
)

TRANSFER_DB = REPO / "data" / "transfer_receipts.db"


def _load_landed_cost_map() -> dict[str, int]:
    if not TRANSFER_DB.is_file():
        return {}
    try:
        conn = sqlite3.connect(str(TRANSFER_DB))
        rows = conn.execute(
            "SELECT product_object_id, unit_cost_cents FROM product_landed_cost_current"
        ).fetchall()
        conn.close()
        return {str(r[0]): int(r[1] or 0) for r in rows if r[0] and r[1]}
    except sqlite3.Error:
        return {}


def _fetch_chunk_with_retry(
    where: dict,
    *,
    credentials_path: str | None,
    retries: int = 3,
) -> list[dict]:
    variables = {"first": PAGE_SIZE, "where": where}
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return fetch_order_items_retail_dashboard(variables, credentials_path=credentials_path)
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    if last_err:
        raise last_err
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest GrowFlow facts into SQLite")
    ap.add_argument("--days", type=int, default=30, help="Trailing store-local days to fetch")
    ap.add_argument("--chunk-days", type=int, default=7)
    ap.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--validation-mode", default="strict", choices=["strict", "warning", "discovery"])
    ap.add_argument("--growflow-credentials", default=None)
    ap.add_argument("--skip-catalog", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    tz = ZoneInfo(cfg.get("sales_timezone") or "America/Chicago")
    creds = args.growflow_credentials or cfg.get("credentials_path")

    end_local = datetime.now(tz).date()
    start_local = end_local - timedelta(days=max(1, args.days) - 1)
    start_utc = datetime(start_local.year, start_local.month, start_local.day, tzinfo=tz).astimezone(timezone.utc)
    end_utc = datetime(end_local.year, end_local.month, end_local.day, 23, 59, 59, 999000, tzinfo=tz).astimezone(
        timezone.utc
    )

    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"
    landed = _load_landed_cost_map()

    conn = connect(args.db_path)
    init_db(conn)
    start_ingest_run(conn, run_id, start_utc.isoformat(), end_utc.isoformat())

    all_nodes: list[dict] = []
    for from_iso, to_iso in iter_sold_at_date_chunks(start_utc, end_utc, args.chunk_days):
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        chunk = _fetch_chunk_with_retry(where, credentials_path=creds)
        print(f"  chunk {from_iso[:10]}..{to_iso[:10]}: {len(chunk)} lines", flush=True)
        all_nodes.extend(chunk)

    lines_upserted = 0
    orders_upserted = 0
    seen_orders: set[str] = set()

    for node in all_nodes:
        order_row, line_row = normalize_order_line(
            node, tz=tz, ingest_run_id=run_id, landed_cost_by_product=landed or None
        )
        if line_row:
            upsert_order_line(conn, line_row)
            lines_upserted += 1
            uid = line_row.get("budtender_user_id")
            name = line_row.get("budtender_name")
            if uid and name:
                upsert_user(conn, str(uid), str(name), None)
        order = first_order_fragment(node)
        store_id, store_name = extract_store(node, order)
        if store_id:
            upsert_store(conn, store_id, store_name or "")
        if order_row and order_row["object_id"] not in seen_orders:
            upsert_order(conn, order_row)
            seen_orders.add(order_row["object_id"])
            orders_upserted += 1

    conn.commit()

    if not args.skip_catalog:
        try:
            for pnode in fetch_products_catalog({"first": PAGE_SIZE}, credentials_path=creds):
                prow = normalize_product(pnode)
                if prow.get("object_id"):
                    upsert_product(conn, prow)
            conn.commit()
        except Exception as e:
            print(f"  catalog fetch warning: {e}", flush=True)

        try:
            for snode in fetch_stores(credentials_path=creds):
                if snode.get("objectId"):
                    upsert_store(conn, str(snode["objectId"]), str(snode.get("Name") or ""))
            conn.commit()
        except Exception as e:
            print(f"  stores fetch warning: {e}", flush=True)

    validation_rows = all_nodes[: min(500, len(all_nodes))]
    validation = validate_and_normalize(
        metric_id="growflow_fact_ingest",
        template_id="order_items_retail_dashboard_v1",
        raw_json={"data": {"findOrderItems": {"edges": [{"node": r} for r in validation_rows]}}},
        request_context={
            "requested_date_range": {"from": start_utc.isoformat(), "to": end_utc.isoformat()},
            "source_script": "scripts/ingest_growflow_facts.py",
            "normalized_row_count": lines_upserted,
        },
        mode=args.validation_mode,
    )
    ok = bool(validation.get("ok"))
    finish_ingest_run(
        conn,
        run_id,
        lines_upserted=lines_upserted,
        orders_upserted=orders_upserted,
        validation_report_path=str(validation.get("report_path") or ""),
        ok=ok,
    )
    conn.close()

    print(f"Ingest run {run_id}: lines={lines_upserted} orders={orders_upserted} ok={ok}", flush=True)
    print(f"Validation: {validation.get('report_path')}", flush=True)
    if args.validation_mode == "strict" and not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
