"""
Build a local SQLite DB of transfer receipts for downstream analytics.

Default scope: Accepted transfers with ReceivedAt >= 2026-04-09T00:00:00Z.

SQLite tables:

- ``transfer_receipts`` / ``transfer_receipt_packages`` — raw receipt + line detail (Growflow ``findTransfers``).
- ``transfer_receipt_sales_staging`` — **join-friendly** package lines: ``product_object_id``,
  ``received_day_local`` (store calendar date), ``received_day_utc`` (UTC calendar date),
  ``days_since_receipt_at_load`` (whole days from ``received_at`` to ingest time, UTC),
  ``received_at_epoch_ms``.
- ``product_landed_cost_current`` — **refined** one row per ``product_object_id``: latest receipt
  line by ``received_at`` (new transfers refresh landed unit cost). Built by ``lib/product_landed_cost_sqlite.py``.

Usage:
  PYTHONPATH=. python scripts/build_transfer_receipts_db.py
  PYTHONPATH=. python scripts/build_transfer_receipts_db.py --since 2026-04-09T00:00:00Z
  PYTHONPATH=. python scripts/build_transfer_receipts_db.py --db data/transfer_receipts.db --leaderboard-top 20
  PYTHONPATH=. python scripts/build_transfer_receipts_db.py --rebuild-costs-only --db data/transfer_receipts.db
  PYTHONPATH=. python scripts/build_transfer_receipts_db.py --export-product-costs-csv data/product_landed_cost_current.csv
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.product_landed_cost_sqlite import (
    export_product_landed_cost_current_csv,
    rebuild_product_landed_cost_current,
)
from lib.data_validation_gateway import validate_and_normalize
from lib.transfer_receipt_export import (
    fetch_transfer_nodes_since,
    load_retail_org_from_config,
    parse_received_at_utc,
    rows_from_transfer_node,
    store_zoneinfo,
)


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transfer_receipts (
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
        CREATE TABLE IF NOT EXISTS transfer_receipt_packages (
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
        CREATE INDEX IF NOT EXISTS idx_trp_transfer ON transfer_receipt_packages(transfer_object_id);
        CREATE INDEX IF NOT EXISTS idx_trp_received_at ON transfer_receipt_packages(received_at);
        CREATE INDEX IF NOT EXISTS idx_trp_from_name ON transfer_receipts(from_name);
        CREATE INDEX IF NOT EXISTS idx_trp_brand ON transfer_receipt_packages(brand_name);

        CREATE TABLE IF NOT EXISTS transfer_receipt_sales_staging (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_slug TEXT NOT NULL,
            transfer_object_id TEXT NOT NULL,
            package_object_id TEXT,
            from_name TEXT,
            product_object_id TEXT,
            brand_name TEXT,
            product_name TEXT,
            package_sku TEXT,
            product_sku TEXT,
            original_qty INTEGER NOT NULL,
            cost_cents INTEGER NOT NULL,
            received_at TEXT NOT NULL,
            received_at_epoch_ms INTEGER,
            received_day_local TEXT,
            received_day_utc TEXT,
            days_since_receipt_at_load INTEGER,
            sales_timezone TEXT,
            loaded_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trss_product ON transfer_receipt_sales_staging(product_object_id);
        CREATE INDEX IF NOT EXISTS idx_trss_day_local ON transfer_receipt_sales_staging(received_day_local);
        CREATE INDEX IF NOT EXISTS idx_trss_day_utc ON transfer_receipt_sales_staging(received_day_utc);
        CREATE INDEX IF NOT EXISTS idx_trss_transfer ON transfer_receipt_sales_staging(transfer_object_id);
        CREATE INDEX IF NOT EXISTS idx_trss_brand_product ON transfer_receipt_sales_staging(brand_name, product_name);
        """
    )


def _days_since_receipt_at_load(received_at: str | None, load_dt: datetime) -> int | None:
    recv = parse_received_at_utc(str(received_at) if received_at else None)
    if recv is None:
        return None
    return int((load_dt - recv).total_seconds() // 86400)


def _upsert(conn: sqlite3.Connection, rows: list[dict]) -> tuple[int, int, int]:
    load_dt = datetime.now(timezone.utc)
    loaded_at = load_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    transfer_ids = sorted({str(r.get("transfer_object_id") or "").strip() for r in rows if r.get("transfer_object_id")})
    if not transfer_ids:
        return (0, 0, 0)
    placeholders = ",".join("?" for _ in transfer_ids)
    conn.execute(
        f"DELETE FROM transfer_receipt_sales_staging WHERE transfer_object_id IN ({placeholders})",
        transfer_ids,
    )
    conn.execute(
        f"DELETE FROM transfer_receipt_packages WHERE transfer_object_id IN ({placeholders})",
        transfer_ids,
    )
    conn.execute(
        f"DELETE FROM transfer_receipts WHERE transfer_object_id IN ({placeholders})",
        transfer_ids,
    )
    receipt_inserted = 0
    package_inserted = 0
    staging_inserted = 0
    seen_hdr: set[str] = set()
    for r in rows:
        tid = str(r.get("transfer_object_id") or "").strip()
        if not tid:
            continue
        if tid not in seen_hdr:
            conn.execute(
                """
                INSERT INTO transfer_receipts (
                    transfer_object_id, transfer_status, received_at, transfer_created_at, transfer_updated_at,
                    from_name, store_object_id, store_name, receiving_store_object_id, receiving_store_name, loaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid,
                    r.get("transfer_status"),
                    r.get("received_at"),
                    r.get("transfer_created_at"),
                    r.get("transfer_updated_at"),
                    r.get("from_name"),
                    r.get("store_object_id"),
                    r.get("store_name"),
                    r.get("receiving_store_object_id"),
                    r.get("receiving_store_name"),
                    loaded_at,
                ),
            )
            seen_hdr.add(tid)
            receipt_inserted += 1
        conn.execute(
            """
            INSERT INTO transfer_receipt_packages (
                transfer_object_id, package_object_id, package_sku, original_qty, current_qty, cost_cents,
                product_object_id, product_name, product_sku, brand_name, received_at, received_date_local,
                sales_timezone, loaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tid,
                r.get("package_object_id"),
                r.get("package_sku"),
                int(r.get("original_qty") or 0),
                int(r.get("current_qty") or 0),
                int(r.get("cost_cents") or 0),
                r.get("product_object_id"),
                r.get("product_name"),
                r.get("product_sku"),
                r.get("brand_name"),
                r.get("received_at"),
                r.get("received_date_local"),
                r.get("sales_timezone"),
                loaded_at,
            ),
        )
        package_inserted += 1

        recv_at = str(r.get("received_at") or "")
        recv_dt = parse_received_at_utc(recv_at)
        utc_day = recv_dt.date().isoformat() if recv_dt else None
        d_days = _days_since_receipt_at_load(recv_at, load_dt)
        epoch_raw = r.get("received_at_epoch_ms")
        epoch_out = int(epoch_raw) if epoch_raw is not None else None
        conn.execute(
            """
            INSERT INTO transfer_receipt_sales_staging (
                org_slug, transfer_object_id, package_object_id, from_name,
                product_object_id, brand_name, product_name, package_sku, product_sku,
                original_qty, cost_cents, received_at, received_at_epoch_ms,
                received_day_local, received_day_utc, days_since_receipt_at_load,
                sales_timezone, loaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(r.get("org_slug") or ""),
                tid,
                r.get("package_object_id"),
                r.get("from_name"),
                r.get("product_object_id"),
                r.get("brand_name"),
                r.get("product_name"),
                r.get("package_sku"),
                r.get("product_sku"),
                int(r.get("original_qty") or 0),
                int(r.get("cost_cents") or 0),
                recv_at,
                epoch_out,
                r.get("received_date_local"),
                utc_day,
                d_days,
                r.get("sales_timezone"),
                loaded_at,
            ),
        )
        staging_inserted += 1
    return (receipt_inserted, package_inserted, staging_inserted)


def _print_supplier_leaderboard(conn: sqlite3.Connection, top_n: int) -> None:
    q = """
        SELECT
            COALESCE(NULLIF(TRIM(r.from_name), ''), '(unknown)') AS supplier,
            COUNT(DISTINCT r.transfer_object_id) AS transfers,
            COALESCE(SUM(p.original_qty), 0) AS units,
            COALESCE(SUM(p.cost_cents), 0) AS landed_cost_cents
        FROM transfer_receipts r
        JOIN transfer_receipt_packages p
          ON p.transfer_object_id = r.transfer_object_id
        GROUP BY supplier
        ORDER BY transfers DESC, units DESC
        LIMIT ?
    """
    rows = conn.execute(q, (int(top_n),)).fetchall()
    print("\nSupplier leaderboard (from local DB):")
    print("supplier | transfers | units | landed_cost")
    for supplier, transfers, units, cost_cents in rows:
        print(f"{supplier} | {transfers} | {units} | ${float(cost_cents or 0)/100:,.2f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="2026-04-09T00:00:00Z", help="ReceivedAt lower bound in UTC ISO")
    ap.add_argument("--status", default="Accepted", help='Transfer status filter (default: "Accepted")')
    ap.add_argument("--db", default=str(_root / "data" / "transfer_receipts.db"), help="SQLite DB path")
    ap.add_argument("--page-size", type=int, default=100, help="GraphQL page size")
    ap.add_argument("--leaderboard-top", type=int, default=15, help="Leaderboard supplier row count")
    ap.add_argument(
        "--validation-mode",
        choices=("strict", "warning", "discovery"),
        default="strict",
        help="Validation gateway mode (strict fail-closed by default).",
    )
    ap.add_argument(
        "--rebuild-costs-only",
        action="store_true",
        help="Skip Growflow fetch; only rebuild product_landed_cost_current from existing package rows.",
    )
    ap.add_argument(
        "--export-product-costs-csv",
        metavar="PATH",
        default="",
        help="After ingest/rebuild, write product_landed_cost_current to this CSV path.",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if args.rebuild_costs_only:
        if not db_path.is_file():
            print(f"DB not found: {db_path}", file=sys.stderr)
            return 1
        conn = sqlite3.connect(str(db_path))
        try:
            _ensure_schema(conn)
            n = rebuild_product_landed_cost_current(conn)
            conn.commit()
            print(f"Rebuilt product_landed_cost_current: {n} product row(s) in {db_path.resolve()}")
            if str(args.export_product_costs_csv or "").strip():
                m = export_product_landed_cost_current_csv(conn, Path(args.export_product_costs_csv.strip()))
                print(f"Wrote {m} row(s) to {Path(args.export_product_costs_csv.strip()).resolve()}")
            _print_supplier_leaderboard(conn, args.leaderboard_top)
        finally:
            conn.close()
        return 0

    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("No credentials: set GROWFLOW_CREDENTIALS_PATH or GROWFLOW_ACCESS_TOKEN", file=sys.stderr)
        return 1

    load_retail_org_from_config()
    org = (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip() or "unknown"
    tz = store_zoneinfo()
    print(f"Fetching transfers for org={org} status={args.status} since={args.since} ...")
    nodes = fetch_transfer_nodes_since(
        received_at_gte=args.since,
        status=args.status,
        page_size=args.page_size,
        credentials_path=cp,
    )
    # Some org responses omit FromName on individual transfers; normalize to keep
    # validation/ingest moving while preserving explicit unknown provenance.
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("FromName") is None or str(n.get("FromName")).strip() == "":
            n["FromName"] = "(unknown)"
    validation = validate_and_normalize(
        metric_id="transfer_receipts",
        template_id="transfer_receipts_accepted_v1",
        raw_json={"data": {"findTransfers": {"nodes": nodes}}},
        request_context={
            "requested_date_range": {"from": args.since, "to": None},
            "status": args.status,
            "source_script": "scripts/build_transfer_receipts_db.py",
        },
        mode=args.validation_mode,
    )
    print(f"Validation report: {validation.get('report_path')}")
    if not validation.get("ok"):
        # Discovery mode can return ok=false with low confidence but no hard failures;
        # allow ingest in that case so downstream experimentation can proceed.
        hard = validation.get("hard_failures") or []
        if args.validation_mode == "discovery" and not hard:
            print("Validation not fully trusted (discovery), proceeding without hard failures.")
        else:
            print(f"Validation blocked trusted output: {validation.get('errors')}", file=sys.stderr)
            return 1
    exported_at = datetime.now(timezone.utc)
    rows: list[dict] = []
    for n in nodes:
        rows.extend(rows_from_transfer_node(n, org_slug=org, exported_at=exported_at, store_tz=tz))
    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_schema(conn)
        t_count, p_count, s_count = _upsert(conn, rows)
        n_cost = rebuild_product_landed_cost_current(conn)
        conn.commit()
        print(
            f"Loaded {t_count} transfers, {p_count} package rows, {s_count} sales-staging rows "
            f"into {db_path.resolve()}"
        )
        print(f"product_landed_cost_current: {n_cost} product row(s) (latest receipt per Product.objectId)")
        if str(args.export_product_costs_csv or "").strip():
            m = export_product_landed_cost_current_csv(conn, Path(args.export_product_costs_csv.strip()))
            print(f"Wrote {m} row(s) to {Path(args.export_product_costs_csv.strip()).resolve()}")
        _print_supplier_leaderboard(conn, args.leaderboard_top)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
