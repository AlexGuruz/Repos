#!/usr/bin/env python3
"""
Build company BI report from growflow_facts.db + sheets_transactions.db.

Replaces the missing company_bi.run_pipeline entrypoint.

  PYTHONPATH=. python scripts/build_company_bi_report.py
  PYTHONPATH=. python scripts/build_company_bi_report.py --months 6
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.platform_config import load_platform_config  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _facts_sales_summary(facts_db: Path, months: int) -> dict[str, Any]:
    if not facts_db.is_file():
        return {"ok": False, "reason": "facts_db_missing", "monthly": []}
    conn = sqlite3.connect(str(facts_db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT substr(sold_date_local, 1, 7) AS ym,
                   COUNT(*) AS lines,
                   SUM(gross_price_cents) AS gross_cents,
                   SUM(net_price_cents) AS net_cents,
                   SUM(COALESCE(cog_cents, 0)) AS cog_cents
            FROM order_lines
            GROUP BY ym
            ORDER BY ym DESC
            LIMIT ?
            """,
            (months,),
        ).fetchall()
        monthly = []
        for r in rows:
            gross = (r["gross_cents"] or 0) / 100.0
            net = (r["net_cents"] or 0) / 100.0
            cog = (r["cog_cents"] or 0) / 100.0
            monthly.append(
                {
                    "ym": r["ym"],
                    "lines": r["lines"],
                    "gross": round(gross, 2),
                    "net": round(net, 2),
                    "cog": round(cog, 2),
                    "gross_profit": round(net - cog, 2),
                }
            )
        return {"ok": True, "monthly": list(reversed(monthly)), "source": str(facts_db)}
    finally:
        conn.close()


def _sheets_summary(sheets_db: Path) -> dict[str, Any]:
    if not sheets_db.is_file():
        return {"ok": False, "reason": "sheets_db_missing", "by_year": []}
    conn = sqlite3.connect(str(sheets_db))
    conn.row_factory = sqlite3.Row
    try:
        sources = conn.execute(
            "SELECT source_key, book_year, last_loaded_at FROM sheet_sources ORDER BY book_year"
        ).fetchall()
        txn = conn.execute(
            """
            SELECT book_year, COUNT(*) AS n,
                   MIN(posted_date) AS min_d, MAX(posted_date) AS max_d,
                   SUM(amount) AS amount_sum
            FROM transactions GROUP BY book_year ORDER BY book_year
            """
        ).fetchall()
        return {
            "ok": True,
            "source": str(sheets_db),
            "sources": [dict(r) for r in sources],
            "by_year": [dict(r) for r in txn],
        }
    except sqlite3.Error as exc:
        return {"ok": False, "reason": str(exc), "by_year": []}
    finally:
        conn.close()


def build_report(*, months: int = 6) -> dict[str, Any]:
    cfg = load_platform_config()
    facts = _facts_sales_summary(cfg.facts_db, months)
    sheets = _sheets_summary(cfg.sheets_transactions_db)
    latest = (facts.get("monthly") or [])[-1] if facts.get("monthly") else None
    summary_parts = []
    if latest:
        summary_parts.append(
            f"POS {latest['ym']}: net ${latest['net']:,.0f} (gross ${latest['gross']:,.0f})"
        )
    if sheets.get("ok"):
        summary_parts.append(f"sheets years={len(sheets.get('by_year') or [])}")
    else:
        summary_parts.append("sheets DB not loaded")
    ok = bool(facts.get("ok"))
    return {
        "ok": ok,
        "built_at": _now(),
        "meta": {
            "org_id": cfg.org_id,
            "built_at": _now(),
            "months": months,
            "validation": {"ok": ok, "errors": [] if ok else [facts.get("reason") or "facts_unavailable"]},
        },
        "summary": "; ".join(summary_parts) if summary_parts else "Company BI report empty",
        "sections": {
            "pos_from_facts": facts,
            "sheets_transactions": sheets,
        },
        "notes": [
            "Do not use company_bi.run_pipeline (removed). Prefer this report + sheets_transactions.db.",
            "Labor/expense depth requires a loaded sheets_transactions.db "
            "(company_bi.scripts.build_sheets_transactions_db).",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build company_bi_report_latest.json")
    ap.add_argument("--months", type=int, default=6)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = load_platform_config()
    report = build_report(months=args.months)
    out = Path(args.out) if args.out else cfg.company_bi_json
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "path": str(out), "summary": report["summary"]}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
