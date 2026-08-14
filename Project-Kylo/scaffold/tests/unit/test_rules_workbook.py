from __future__ import annotations

import importlib

from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


def test_extract_spreadsheet_id_accepts_url_and_raw_id():
    assert extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0") == "abc123"
    assert extract_spreadsheet_id("raw-sheet-id") == "raw-sheet-id"
    assert extract_spreadsheet_id("https://example.com/not-a-sheet") == ""


def test_rules_management_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")
    cfg = {"rules": {"management_spreadsheet_id": "cfg-sheet"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet"


def test_rules_management_id_reads_nested_config(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg-sheet/edit"}}

    assert get_rules_management_spreadsheet_id(cfg) == "cfg-sheet"


def test_kafka_promote_consumer_imports(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    module = importlib.import_module("services.bus.kafka_consumer_promote")

    assert hasattr(module, "process_message")
