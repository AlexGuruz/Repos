from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Any


class _Cfg:
    def __init__(self, data: dict[str, Any]):
        self.data = data

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


class _Rule:
    def __init__(self, source: str):
        self.source = source
        self.target_sheet = "Target"
        self.target_header = "Amount"
        self.company_id = "JGD"
        self.approved = True


def test_poster_audit_flag_lookup_uses_current_matched_row(monkeypatch, tmp_path: Path):
    from services.posting import jgdtruth_poster as poster
    from services.state.store import State

    cfg = _Cfg(
        {
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/inputSid",
                    }
                ]
            },
            "google": {"service_account_json_path": str(tmp_path / "service-account.json")},
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": False,
                "append_transactions": False,
            },
            "runtime": {"dry_run": False},
            "intake": {"extra_tabs": []},
            "intake_static_dates": {"header_row": 1, "first_row": 2},
        }
    )
    txns = [
        {
            "txn_uid": "txn-1",
            "company_id": "JGD",
            "posted_date": "2026-01-01",
            "amount_cents": 100,
            "description": "First",
            "row_index_0based": 1,
            "source_tab": "TRANSACTIONS",
            "source_spreadsheet_id": "inputSid",
            "posted_flag": False,
        },
        {
            "txn_uid": "txn-2",
            "company_id": "JGD",
            "posted_date": "2026-01-01",
            "amount_cents": 200,
            "description": "Second",
            "row_index_0based": 2,
            "source_tab": "TRANSACTIONS",
            "source_spreadsheet_id": "inputSid",
            "posted_flag": False,
        },
    ]

    class _Processor:
        def __init__(self, *args, **kwargs):
            pass

        def parse_transactions(self):
            return iter(txns)

    class _Service:
        def spreadsheets(self):
            return self

        def values(self):
            return self

        def get(self, **kwargs):
            return object()

        def batchGet(self, **kwargs):
            return object()

        def batchUpdate(self, **kwargs):
            return object()

        def append(self, **kwargs):
            return object()

    def fake_execute(req, policy=None, label=""):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 1, "title": "Target"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "Target!1:1", "values": [["Date", "Amount"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"]]}
        if label in {"target:batchUpdate_values", "target:repair_batchUpdate"}:
            return {}
        return {}

    calls: list[dict[str, Any]] = []

    def fake_is_flagged(**kwargs):
        calls.append(kwargs)
        return False

    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_2026")
    monkeypatch.setattr(poster, "load_config", lambda: cfg)
    monkeypatch.setattr(poster, "_get_service", lambda: _Service())

    def fake_download(*args, **kwargs):
        if kwargs.get("sheet_name_override") == "BANK":
            raise RuntimeError("missing tab")
        return "csv"

    monkeypatch.setattr(poster, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr("services.intake.csv_processor.PettyCashCSVProcessor", _Processor)
    monkeypatch.setattr(
        poster,
        "fetch_rules_from_jgdtruth",
        lambda company: {"First": _Rule("First"), "Second": _Rule("Second")},
    )
    monkeypatch.setattr(poster, "google_api_execute", fake_execute)
    monkeypatch.setattr(poster, "load_state", lambda: State())
    monkeypatch.setattr(poster, "save_state", lambda state: None)
    monkeypatch.setattr(poster, "is_txn_flagged", fake_is_flagged)

    result = poster.run("JGD")

    assert result["posting_complete"] is True
    assert [c["description"] for c in calls] == ["First", "Second"]
    assert [c["posted_date"] for c in calls] == ["2026-01-01", "2026-01-01"]


def test_watcher_does_not_ack_partial_posting_failure(monkeypatch):
    from kylo import watcher_runtime as watcher

    cfg = _Cfg(
        {
            "posting": {"sheets": {"apply": True}},
            "runtime": {"mode": "post", "circuit_breaker": {"max_consecutive_failures": 5}},
        }
    )
    state = {
        "seen": {"JGD": {"rules": "r1", "intake": "old"}},
        "acked": {"JGD": {"rules": "r1", "intake": "old"}},
    }
    saved: list[dict[str, Any]] = []

    monkeypatch.setattr(watcher, "load_config", lambda: cfg)
    monkeypatch.setattr(watcher, "is_audit_mode", lambda cfg: False)
    monkeypatch.setattr(watcher, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher, "rules_checksum", lambda company: "r1")
    monkeypatch.setattr(watcher, "intake_checksum", lambda cfg, company: "new")
    monkeypatch.setattr(watcher, "_load_state", lambda: state)
    monkeypatch.setattr(watcher, "_save_state", lambda s: saved.append(s.copy()))

    from services.posting import jgdtruth_poster

    monkeypatch.setattr(
        jgdtruth_poster,
        "run",
        lambda company, rules_changed=False: {
            "posting_complete": False,
            "failed_ranges_count": 1,
            "cells_written": 1,
        },
    )

    result = watcher.tick_once(["JGD"])

    assert result["posting_attempted"] is True
    assert saved[-1]["acked"]["JGD"] == {"rules": "r1", "intake": "old"}
    assert saved[-1]["circuit_breaker"]["consecutive_failures"] == 1


def test_kafka_promote_import_resolves_rules_workbook(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class _Consumer:
        pass

    fake_aiokafka.AIOKafkaConsumer = _Consumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "rulesSid")
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert hasattr(mod, "load_config")
    assert mod.get_rules_management_spreadsheet_id(None) == "rulesSid"

