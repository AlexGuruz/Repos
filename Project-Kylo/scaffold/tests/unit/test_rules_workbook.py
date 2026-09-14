from __future__ import annotations

import importlib
import sys
import types

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_workbook_resolves_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/rules-sheet-123/edit#gid=0"
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "rules-sheet-123"


def test_rules_workbook_env_id_wins(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-456")

    cfg = {"rules": {"management_spreadsheet_id": "config-sheet-789"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet-456"


def test_kafka_promote_consumer_imports_with_fake_aiokafka(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")
    fake_aiokafka.AIOKafkaConsumer = object
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert mod.load_config is not None
    assert mod.get_rules_management_spreadsheet_id is not None
