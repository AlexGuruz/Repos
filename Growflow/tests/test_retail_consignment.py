"""Tests for retail consignment payload builder."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lib.consignment_store import CohortRow, DailyVendorSummaryRow, ensure_schema, insert_cohort, upsert_vendor_summary
from lib.retail_dashboard.consignment import (
    DEFAULT_KPIS,
    build_consignment,
    enrich_consignment_dict,
    payload_to_dict,
)


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    ensure_schema(conn)
    insert_cohort(
        conn,
        CohortRow(
            transfer_object_id="TR-001",
            vendor_id="vendor_a",
            from_name="Vendor A",
            received_at="2026-06-01T12:00:00Z",
            received_local="2026-06-01",
            due_local="2026-07-01",
            net_days=30,
            status="active",
            units_received=100,
            units_sold=0,
            units_remaining=100,
        ),
        packages=[],
    )
    upsert_vendor_summary(
        conn,
        DailyVendorSummaryRow(
            sales_local_date="2026-06-10",
            vendor_id="vendor_a",
            units_sold=5,
            accrual_cents=5000,
            backlog_cents=12000,
            recommended_pull_cents=4000,
            confirmed_cents=0,
            status="DUE SOON",
            sheet_row=None,
        ),
    )
    conn.commit()
    conn.close()


CONTRACT_KEYS = (
    "generated_at",
    "status",
    "kpis",
    "active_transfers",
    "latest_by_vendor",
    "daily_ledger",
)


def _assert_contract_shape(d: dict) -> None:
    for key in CONTRACT_KEYS:
        assert key in d, f"missing contract key: {key}"
    assert d["generated_at"]
    assert d["status"] in ("ok", "empty")
    assert isinstance(d["kpis"], dict)
    assert isinstance(d["active_transfers"], list)
    assert isinstance(d["latest_by_vendor"], list)
    assert isinstance(d["daily_ledger"], list)


def test_build_consignment_from_db(tmp_path: Path):
    db = tmp_path / "consignment.db"
    _seed_db(db)
    payload = build_consignment(db_path=db)
    d = payload_to_dict(payload)
    _assert_contract_shape(d)
    assert d["meta"]["validation"]["ok"] is True
    assert d["status"] == "ok"
    assert d["kpi_strip"]["vendors_active"] >= 0
    assert len(d["active_transfers"]) == 1
    assert d["active_transfers"][0]["transfer_id"] == "TR-001"
    assert len(d["latest_by_vendor"]) == 1
    assert d["latest_by_vendor"][0]["recommended_pull_usd"] == 40.0
    assert len(d["daily_ledger"]) >= 1


def test_empty_consignment(tmp_path: Path):
    payload = build_consignment(db_path=tmp_path / "missing.db")
    d = payload_to_dict(payload)
    _assert_contract_shape(d)
    assert payload.meta["validation"]["ok"] is False
    assert "consignment_db_missing" in payload.meta["validation"]["errors"]
    assert d["status"] == "empty"
    assert d["kpis"]["today_recommended_pull_usd"] == 0.0
    assert d["active_transfers"] == []
    assert d["latest_by_vendor"] == []
    assert d["daily_ledger"] == []


def test_consignment_payload_shape():
    d = payload_to_dict(build_consignment(db_path=Path("missing.db.test")))
    for key in ("meta", "kpi_strip", "active_transfers", "latest_day_by_vendor", "daily_ledger"):
        assert key in d
    assert "validation" in d["meta"]
    _assert_contract_shape(d)


def test_enrich_cached_payload_without_aliases():
    cached = {
        "meta": {"built_at": "2026-06-10T12:00:00Z", "validation": {"ok": True}},
        "kpi_strip": {"open_backlog_usd": 100.0},
        "active_transfers": [],
        "latest_day_by_vendor": [{"vendor_id": "v1"}],
        "daily_ledger": [],
    }
    out = enrich_consignment_dict(cached)
    _assert_contract_shape(out)
    assert out["kpis"]["open_backlog_usd"] == 100.0
    assert out["latest_by_vendor"][0]["vendor_id"] == "v1"


def test_empty_kpis_default_when_missing():
    out = enrich_consignment_dict({"meta": {"validation": {"ok": False}}})
    assert out["kpis"] == DEFAULT_KPIS


def test_get_consignment_skips_stale_cache_when_db_missing(tmp_path, monkeypatch):
    from dashboard.backend import main as api_main

    stale = {
        "meta": {
            "built_at": "2026-01-01T00:00:00Z",
            "source_exists": True,
            "validation": {"ok": True},
        },
        "kpi_strip": {"open_backlog_usd": 999.0},
        "active_transfers": [{"transfer_id": "stale"}],
        "latest_day_by_vendor": [],
        "daily_ledger": [],
    }
    json_path = tmp_path / "retail_consignment_latest.json"
    json_path.write_text(json.dumps(stale), encoding="utf-8")
    missing_db = tmp_path / "no_consignment.db"

    monkeypatch.setattr(api_main, "DEFAULT_CONSIGNMENT_JSON", json_path)
    monkeypatch.setattr(api_main, "consignment_db_path", lambda: missing_db)

    result = api_main.get_consignment()
    assert result["status"] == "empty"
    assert result["active_transfers"] == []
    assert result["kpis"]["today_recommended_pull_usd"] == 0.0
