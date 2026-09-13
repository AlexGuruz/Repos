from __future__ import annotations

import importlib
import sys
import types


def test_rules_management_spreadsheet_id_prefers_explicit_id(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "explicit-id")
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/env-url-id/edit",
    )

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id() == "explicit-id"


def test_rules_management_spreadsheet_id_extracts_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/config-url-id/edit#gid=0",
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "config-url-id"


def test_promote_consumer_imports_with_kafka_stub(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class AIOKafkaConsumer:  # pragma: no cover - never instantiated by the import smoke
        pass

    fake_aiokafka.AIOKafkaConsumer = AIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)

    module_name = "services.bus.kafka_consumer_promote"
    sys.modules.pop(module_name, None)
    mod = importlib.import_module(module_name)

    assert hasattr(mod, "process_message")
