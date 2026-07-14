"""
Consignment tab payload from ``data/consignment.db`` (read-only v1).

Built by ``scripts/build_retail_consignment.py``; served via FastAPI.
No GraphQL at request time.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lib.consignment_allocation import kpi_totals
from lib.consignment_config import load_sheet_config, load_vendors
from lib.consignment_store import (
    DailyVendorSummaryRow,
    _summary_from_row,
    cohort_packages,
    list_active_cohorts,
    open_store,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONSIGNMENT_JSON = REPO_ROOT / "data" / "retail_consignment_latest.json"

DEFAULT_KPIS: dict[str, Any] = {
    "today_recommended_pull_usd": 0.0,
    "open_backlog_usd": 0.0,
    "due_in_7_usd": 0.0,
    "overdue_usd": 0.0,
    "mtd_confirmed_usd": 0.0,
    "vendors_active": 0,
    "status_chip": None,
    "latest_date": None,
}


def consignment_db_path(db_path: Path | str | None = None) -> Path:
    if db_path:
        return Path(db_path)
    cfg = load_sheet_config()
    raw = cfg.get("db_path") or REPO_ROOT / "data" / "consignment.db"
    p = Path(raw)
    return p if p.is_absolute() else REPO_ROOT / p


def _cents_to_usd(cents: int | float | None) -> float:
    return round(float(cents or 0) / 100.0, 2)


def _load_all_summaries(conn: sqlite3.Connection) -> list[DailyVendorSummaryRow]:
    rows = conn.execute(
        "SELECT * FROM daily_vendor_summary ORDER BY sales_local_date DESC, vendor_id"
    ).fetchall()
    return [_summary_from_row(r) for r in rows]


def _vendor_display_map() -> dict[str, str]:
    return {v.id: v.from_name for v in load_vendors()}


@dataclass
class ConsignmentPayload:
    meta: dict[str, Any]
    kpi_strip: dict[str, Any]
    active_transfers: list[dict[str, Any]]
    latest_day_by_vendor: list[dict[str, Any]]
    daily_ledger: list[dict[str, Any]]


def build_consignment(
    *,
    db_path: Path | str | None = None,
    run_id: str | None = None,
) -> ConsignmentPayload:
    cfg = load_sheet_config()
    db = consignment_db_path(db_path)
    tz = ZoneInfo(str(cfg.get("sales_timezone") or "America/Chicago"))
    today = datetime.now(tz).date()
    vendor_names = _vendor_display_map()

    if not db.is_file():
        return ConsignmentPayload(
            meta={
                "run_id": run_id or "cons_empty",
                "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "source_db": str(db),
                "source_exists": False,
                "validation": {"ok": False, "errors": ["consignment_db_missing"]},
            },
            kpi_strip=dict(DEFAULT_KPIS),
            active_transfers=[],
            latest_day_by_vendor=[],
            daily_ledger=[],
        )

    conn = open_store(db)
    try:
        summaries = _load_all_summaries(conn)
        latest_date = max((s.sales_local_date for s in summaries), default=None)
        kpis = kpi_totals(summaries, latest_date=latest_date, today=today)

        active = list_active_cohorts(conn)
        active_transfers: list[dict[str, Any]] = []
        for c in active:
            pkgs = cohort_packages(conn, c.transfer_object_id)
            original_cents = sum(p.original_qty * p.unit_cost_cents for p in pkgs)
            active_transfers.append({
                "transfer_id": c.transfer_object_id,
                "vendor_id": c.vendor_id,
                "vendor_name": vendor_names.get(c.vendor_id, c.from_name),
                "received_date": c.received_local,
                "due_date": c.due_local,
                "original_amount_usd": _cents_to_usd(original_cents),
                "units_received": c.units_received,
                "units_sold": c.units_sold,
                "units_remaining": c.units_remaining,
                "status": c.status,
                "net_days": c.net_days,
            })

        latest_rows = [s for s in summaries if latest_date and s.sales_local_date == latest_date]
        latest_day_by_vendor = [
            {
                "vendor_id": s.vendor_id,
                "vendor_name": vendor_names.get(s.vendor_id, s.vendor_id),
                "accrual_usd": _cents_to_usd(s.accrual_cents),
                "backlog_usd": _cents_to_usd(s.backlog_cents),
                "recommended_pull_usd": _cents_to_usd(s.recommended_pull_cents),
                "confirmed_usd": _cents_to_usd(s.confirmed_cents),
                "status": s.status or "OK",
                "units_sold": s.units_sold,
            }
            for s in sorted(latest_rows, key=lambda x: -(x.recommended_pull_cents or 0))
        ]

        daily_ledger = [
            {
                "date": s.sales_local_date,
                "vendor_id": s.vendor_id,
                "vendor_name": vendor_names.get(s.vendor_id, s.vendor_id),
                "accrual_usd": _cents_to_usd(s.accrual_cents),
                "backlog_usd": _cents_to_usd(s.backlog_cents),
                "recommended_pull_usd": _cents_to_usd(s.recommended_pull_cents),
                "confirmed_usd": _cents_to_usd(s.confirmed_cents),
                "status": s.status,
                "source": "daily_vendor_summary",
            }
            for s in summaries[:500]
        ]

        kpi_strip = {
            "today_recommended_pull_usd": _cents_to_usd(kpis.get("today_recommended_pull_cents")),
            "open_backlog_usd": _cents_to_usd(kpis.get("open_backlog_cents")),
            "due_in_7_usd": _cents_to_usd(kpis.get("due_in_7_cents")),
            "overdue_usd": _cents_to_usd(kpis.get("overdue_cents")),
            "mtd_confirmed_usd": _cents_to_usd(kpis.get("confirmed_mtd_cents")),
            "vendors_active": kpis.get("vendors_active", 0),
            "status_chip": kpis.get("status_chip"),
            "latest_date": latest_date,
        }
    finally:
        conn.close()

    built = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = {
        "run_id": run_id or f"cons_{built.replace(':', '').replace('-', '')[:15]}",
        "built_at": built,
        "source_db": str(db),
        "source_exists": True,
        "latest_date": latest_date,
        "row_count": len(summaries),
        "validation": {"ok": True, "errors": []},
    }

    return ConsignmentPayload(
        meta=meta,
        kpi_strip=kpi_strip,
        active_transfers=active_transfers,
        latest_day_by_vendor=latest_day_by_vendor,
        daily_ledger=daily_ledger,
    )


def enrich_consignment_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Ensure stable contract keys on cached or live payloads."""
    kpi = d.get("kpi_strip") or d.get("kpis") or dict(DEFAULT_KPIS)
    out = dict(d)
    out["kpi_strip"] = kpi
    out["active_transfers"] = out.get("active_transfers") or []
    out["latest_day_by_vendor"] = out.get("latest_day_by_vendor") or out.get("latest_by_vendor") or []
    out["daily_ledger"] = out.get("daily_ledger") or []
    out["generated_at"] = out.get("generated_at") or out.get("meta", {}).get("built_at")
    vok = out.get("meta", {}).get("validation", {}).get("ok")
    out["status"] = out.get("status") or ("ok" if vok else "empty")
    out["kpis"] = kpi
    out["latest_by_vendor"] = out.get("latest_by_vendor") or out["latest_day_by_vendor"]
    return out


def payload_to_dict(payload: ConsignmentPayload) -> dict[str, Any]:
    kpi = payload.kpi_strip if payload.kpi_strip else dict(DEFAULT_KPIS)
    body = {
        "meta": payload.meta,
        "kpi_strip": kpi,
        "active_transfers": payload.active_transfers,
        "latest_day_by_vendor": payload.latest_day_by_vendor,
        "daily_ledger": payload.daily_ledger,
    }
    # Contract aliases for API consumers (stable top-level keys).
    body["generated_at"] = payload.meta.get("built_at")
    body["status"] = "ok" if payload.meta.get("validation", {}).get("ok") else "empty"
    body["kpis"] = kpi
    body["latest_by_vendor"] = payload.latest_day_by_vendor
    return enrich_consignment_dict(body)
