#!/usr/bin/env python3
"""
Pull financial Google Sheets into a local SQLite database (filterable, queryable).

Uses the stashbox service account (default: E:/secrets/gcp/sa.json).

Run from Growflow repo root:
  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db
  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db --db data/sheets_transactions.db
  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db --source year_2025
  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db --summary

Example queries (sqlite3):
  SELECT posted_date, company, source, amount, txn_type
  FROM transactions WHERE book_year = 2025 AND company LIKE '%NUGZ%' ORDER BY posted_date;

  SELECT log_date, source_name, c20, c10, line_total
  FROM money_log_lines WHERE book_year = 2023 AND source_name LIKE '%Reg%' ORDER BY log_date;
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from company_bi.lib.sheets_transactions_db import (
    get_db_path,
    ingest_all_sources,
    load_sheets_db_config,
)


def _print_summary(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        print(f"\nDatabase: {db_path}\n")
        sources = conn.execute(
            """
            SELECT source_key, book_year, spreadsheet_title, tab_name, layout_type, last_loaded_at
            FROM sheet_sources ORDER BY book_year
            """
        ).fetchall()
        print("Sources (by book_year):")
        for s in sources:
            print(
                f"  {s['book_year']}: {s['source_key']} — {s['spreadsheet_title']} / {s['tab_name']} "
                f"({s['layout_type']}) @ {s['last_loaded_at']}"
            )

        txn = conn.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]
        ml = conn.execute("SELECT COUNT(*) AS n FROM money_log_lines").fetchone()["n"]
        print(f"\nRows: transactions={txn:,}  money_log_lines={ml:,}")

        print("\nTransactions by book_year:")
        for row in conn.execute(
            """
            SELECT book_year, COUNT(*) AS n, MIN(posted_date) AS min_d, MAX(posted_date) AS max_d
            FROM transactions GROUP BY book_year ORDER BY book_year
            """
        ):
            print(f"  {row['book_year']}: {row['n']:,} rows ({row['min_d']} .. {row['max_d']})")

        print("\nMoney log by book_year:")
        for row in conn.execute(
            """
            SELECT book_year, COUNT(*) AS n, MIN(log_date) AS min_d, MAX(log_date) AS max_d
            FROM money_log_lines GROUP BY book_year ORDER BY book_year
            """
        ):
            print(f"  {row['book_year']}: {row['n']:,} rows ({row['min_d']} .. {row['max_d']})")
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build SQLite DB from Google Sheets transactions")
    ap.add_argument("--db", default=None, help="SQLite output path (default from config)")
    ap.add_argument("--source", action="append", dest="sources", help="Only ingest this source_key (repeatable)")
    ap.add_argument("--sheets-service-account", default=None, help="Override stashbox JSON path")
    ap.add_argument("--summary", action="store_true", help="Print DB summary only (no ingest)")
    args = ap.parse_args()

    cfg = load_sheets_db_config()
    db_path = Path(args.db) if args.db else get_db_path(cfg)

    if args.summary:
        if not db_path.exists():
            print(f"Database not found: {db_path}", file=sys.stderr)
            return 1
        _print_summary(db_path)
        return 0

    service = None
    if args.sheets_service_account:
        from lib.stashbox_sheets_auth import sheets_service

        service = sheets_service(args.sheets_service_account)

    print("Pulling sheets via stashbox service account...", flush=True)
    try:
        result = ingest_all_sources(
            db_path=db_path,
            service=service,
            config=cfg,
            source_keys=args.sources,
        )
    except Exception as exc:
        print(f"Ingest failed: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {result['transaction_rows']:,} transaction rows and {result['money_log_rows']:,} money-log rows")
    print(f"Database: {result['db_path']} (batch_id={result['batch_id']})")
    _print_summary(db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
