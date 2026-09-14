from __future__ import annotations

import asyncio
import importlib
import sys
import types
from types import SimpleNamespace


class _FakeCursor:
    def __init__(self, db: "_FakeDb") -> None:
        self.db = db
        self.sql = ""

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def execute(self, sql: str, params: object = None) -> None:
        self.sql = " ".join(str(sql).lower().split())
        self.db.statements.append(self.sql)

    def fetchall(self):
        if "from app.pending_txns" in self.sql:
            return list(self.db.pending_items)
        if "from app.rules_active" in self.sql:
            return list(self.db.active_rules)
        return []

    def fetchone(self):
        if "from control.sheet_posts" in self.sql:
            return (1,) if self.db.seen_sheet_post else None
        return None


class _FakeConn:
    def __init__(self, db: "_FakeDb") -> None:
        self.db = db

    def __enter__(self) -> "_FakeConn":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def cursor(self, *args: object, **kwargs: object) -> _FakeCursor:
        return _FakeCursor(self.db)

    def commit(self) -> None:
        self.db.commits += 1


class _FakeDb:
    def __init__(self) -> None:
        self.pending_items = [
            {
                "txn_uid": "txn-1",
                "date": "2026-01-02",
                "source": "Vendor",
                "amount_cents": 1234,
            }
        ]
        self.active_rules = [
            {
                "rule_json": {
                    "source": "Vendor",
                    "target_sheet": "NUGZ EXPENSES",
                    "target_header": "Supplies",
                }
            }
        ]
        self.seen_sheet_post = False
        self.statements: list[str] = []
        self.commits = 0

    def connect(self, *_args: object, **_kwargs: object) -> _FakeConn:
        return _FakeConn(self)

    def inserted_sheet_posts(self) -> bool:
        return any("insert into control.sheet_posts" in stmt for stmt in self.statements)


def _routing() -> SimpleNamespace:
    return SimpleNamespace(
        db_dsn_rw="postgresql://example/kylo",
        db_schema="app",
        spreadsheet_id="sheet-id",
        tab_pending="NUGZ Pending",
        tab_active="NUGZ Active",
    )


def _txn_msg() -> SimpleNamespace:
    return SimpleNamespace(
        ingest_batch_id=1,
        batch_id="batch-1",
        company_id="NUGZ",
        routing=_routing(),
    )


def _promote_msg() -> SimpleNamespace:
    return SimpleNamespace(company_id="NUGZ", routing=_routing())


def _stub_async_kafka(monkeypatch) -> None:
    aiokafka = types.ModuleType("aiokafka")
    aiokafka.AIOKafkaConsumer = object
    monkeypatch.setitem(sys.modules, "aiokafka", aiokafka)


def _stub_sync_kafka(monkeypatch) -> None:
    kafka = types.ModuleType("kafka")
    kafka.KafkaConsumer = object
    errors = types.ModuleType("kafka.errors")
    errors.NoBrokersAvailable = RuntimeError
    kafka.errors = errors
    monkeypatch.setitem(sys.modules, "kafka", kafka)
    monkeypatch.setitem(sys.modules, "kafka.errors", errors)


def _import_module(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def _fail_sheets_call(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("shadow mode must not touch Google Sheets")


def test_async_txns_shadow_mode_does_not_write_sheets_or_sheet_posts(monkeypatch):
    _stub_async_kafka(monkeypatch)
    mod = _import_module("services.bus.kafka_consumer_txns")
    db = _FakeDb()
    monkeypatch.setattr(mod.psycopg2, "connect", db.connect)
    monkeypatch.setattr(mod, "DO_POST", False)
    monkeypatch.setattr(mod, "MoverService", lambda *a, **k: SimpleNamespace(move_batch=lambda *_a, **_k: None))
    monkeypatch.setattr(mod, "triage_company_batch", lambda *a, **k: None)
    monkeypatch.setattr(mod.poster, "_get_service", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "ensure_company_tabs", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "build_pending_batch_update", _fail_sheets_call)

    asyncio.run(mod.process_message(_txn_msg()))

    assert not db.inserted_sheet_posts()
    assert db.commits == 0


def test_sync_txns_shadow_mode_does_not_write_sheets_or_sheet_posts(monkeypatch):
    _stub_sync_kafka(monkeypatch)
    mod = _import_module("services.bus.kafka_consumer_txns_sync")
    db = _FakeDb()
    monkeypatch.setattr(mod.psycopg2, "connect", db.connect)
    monkeypatch.setattr(mod, "DO_POST", False)
    monkeypatch.setattr(mod, "MoverService", lambda *a, **k: SimpleNamespace(move_batch=lambda *_a, **_k: None))
    monkeypatch.setattr(mod, "triage_company_batch", lambda *a, **k: None)
    monkeypatch.setattr(mod.poster, "_get_service", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "ensure_company_tabs", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "build_pending_batch_update", _fail_sheets_call)

    mod.process_message(_txn_msg())

    assert not db.inserted_sheet_posts()
    assert db.commits == 0


def test_promote_shadow_mode_does_not_write_sheets_or_sheet_posts(monkeypatch):
    _stub_async_kafka(monkeypatch)
    mod = _import_module("services.bus.kafka_consumer_promote")
    db = _FakeDb()
    monkeypatch.setattr(mod.psycopg2, "connect", db.connect)
    monkeypatch.setattr(mod, "DO_POST", False)
    monkeypatch.setattr(mod, "rules_promote", lambda *a, **k: {})
    monkeypatch.setattr(mod, "replay_after_promotion", lambda *a, **k: None)
    monkeypatch.setattr(mod, "get_rules_management_spreadsheet_id", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "_get_service", _fail_sheets_call)
    monkeypatch.setattr(mod.poster, "ensure_company_tabs", _fail_sheets_call)

    asyncio.run(mod.process_message(_promote_msg()))

    assert not db.inserted_sheet_posts()
    assert db.commits == 0


def test_rules_management_spreadsheet_id_resolves_config_url(monkeypatch):
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/abc123_DEF-456/edit#gid=0"
        }
    }
    assert get_rules_management_spreadsheet_id(cfg) == "abc123_DEF-456"
