from __future__ import annotations

import importlib
import sys
import types


def test_rules_management_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-id")

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id() == "env-sheet-id"


def test_rules_management_id_reads_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    class Config:
        def get(self, key, default=None):
            values = {
                "rules.management_spreadsheet_id": None,
                "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/config-sheet-id/edit#gid=0",
            }
            return values.get(key, default)

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id(Config()) == "config-sheet-id"


def test_rules_management_id_reads_config_direct_id(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    class Config:
        def get(self, key, default=None):
            values = {
                "rules.management_spreadsheet_id": "direct-config-id",
                "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/ignored/edit",
            }
            return values.get(key, default)

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id(Config()) == "direct-config-id"


def test_kafka_promote_consumer_imports_with_restored_common_helpers(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class FakeConsumer:
        pass

    fake_aiokafka.AIOKafkaConsumer = FakeConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)

    module_name = "services.bus.kafka_consumer_promote"
    sys.modules.pop(module_name, None)
    module = importlib.import_module(module_name)

    assert module.get_rules_management_spreadsheet_id is not None
    assert module.load_config is not None
