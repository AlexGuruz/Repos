from __future__ import annotations

import sys
import types

from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


def test_extract_spreadsheet_id_from_google_url():
    assert (
        extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/spreadsheet-id-123/edit#gid=0")
        == "spreadsheet-id-123"
    )


def test_get_rules_management_spreadsheet_id_from_config():
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/rules-book/edit"}}

    assert get_rules_management_spreadsheet_id(cfg) == "rules-book"


def test_kafka_promote_consumer_imports_without_optional_kafka_package(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class FakeConsumer:
        pass

    fake_aiokafka.AIOKafkaConsumer = FakeConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    fake_psycopg2 = types.ModuleType("psycopg2")
    fake_psycopg2.connect = lambda *args, **kwargs: None
    fake_extras = types.ModuleType("psycopg2.extras")
    fake_extras.RealDictCursor = object
    fake_extras.execute_values = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "psycopg2", fake_psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", fake_extras)
    fake_poster = types.ModuleType("services.sheets.poster")
    fake_poster._get_service = lambda: None
    fake_poster.ensure_company_tabs = lambda *args, **kwargs: {"requests": []}
    fake_poster._fetch_meta = lambda *args, **kwargs: ({}, {})
    fake_poster.build_tab_name = lambda company_id, name: f"{company_id} {name}"
    monkeypatch.setitem(sys.modules, "services.sheets.poster", fake_poster)

    import services.bus.kafka_consumer_promote as consumer

    assert consumer.AIOKafkaConsumer is FakeConsumer
