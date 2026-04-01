#!/usr/bin/env python3
"""
Ingest GrowFlow API order items (sales/inventory data) into the configured database for easier
queries and analytics. Uses the same API and date window as the BI pipeline.

Run from Growflow repo root:
  python -m company_bi.scripts.ingest_growflow_to_db
  python -m company_bi.scripts.ingest_growflow_to_db --months 12
  python -m company_bi.scripts.ingest_growflow_to_db --growflow-credentials "E:/secrets/gcp/growflowapi.txt"

First run: ensure the table exists. SQLite (default): created automatically. Postgres: run
  db/001_growflow_order_items_pg.sql
once. Config: company_bi/config/sources.yaml under database.path (SQLite) or database.dsn (Postgres).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from company_bi.lib.sources import fetch_growflow_order_items, load_sources_config
from company_bi.lib.growflow_db import ingest_order_items, get_db_path, get_dsn


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest GrowFlow order items into database")
    ap.add_argument("--months", type=int, default=24, help="Months of data to fetch (default 24)")
    ap.add_argument("--growflow-credentials", default=None, help="Path to GrowFlow API credentials file")
    args = ap.parse_args()

    cfg = load_sources_config()
    growflow_cfg = cfg.get("growflow", {})
    creds_path = (
        args.growflow_credentials
        or os.environ.get("GROWFLOW_CREDENTIALS_PATH")
        or growflow_cfg.get("default_credentials_path")
    )
    if not creds_path and Path("E:/secrets/gcp/growflowapi.txt").exists():
        creds_path = "E:/secrets/gcp/growflowapi.txt"

    print("Fetching order items from GrowFlow API...", flush=True)
    try:
        nodes = fetch_growflow_order_items(months_back=args.months, credentials_path=creds_path)
    except Exception as e:
        print(f"Error fetching from API: {e}", file=sys.stderr)
        return 1

    print(f"Fetched {len(nodes)} order item nodes.", flush=True)
    if not nodes:
        print("Nothing to ingest.", flush=True)
        return 0

    db_path = get_db_path()
    dsn = get_dsn()
    if dsn:
        print("Writing to Postgres...", flush=True)
    else:
        print(f"Writing to SQLite: {db_path}", flush=True)

    try:
        written = ingest_order_items(nodes)
    except Exception as e:
        print(f"Error ingesting: {e}", file=sys.stderr)
        return 1

    print(f"Ingested {written} rows into growflow_order_items.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
