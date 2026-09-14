from __future__ import annotations

import importlib
import sys
import types


def test_rules_management_spreadsheet_id_from_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/sheet-12345/edit#gid=0"
        }
    }
    assert get_rules_management_spreadsheet_id(cfg) == "sheet-12345"


def test_rules_management_spreadsheet_id_env_override(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/config-sheet/edit"}}
    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet"


def test_rules_management_workbook_url_env_override(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/env-url-sheet/edit",
    )

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    cfg = {"rules": {"management_spreadsheet_id": "config-sheet"}}
    assert get_rules_management_spreadsheet_id(cfg) == "env-url-sheet"


def test_kafka_promote_consumer_imports_without_real_aiokafka(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class AIOKafkaConsumer:  # pragma: no cover - only used as an import stub
        pass

    fake_aiokafka.AIOKafkaConsumer = AIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert hasattr(mod, "process_message")
