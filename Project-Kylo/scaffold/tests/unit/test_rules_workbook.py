from __future__ import annotations

import importlib
import sys
import types

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class DictConfig:
    def __init__(self, data):
        self.data = data

    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def test_rules_workbook_resolves_env_spreadsheet_id(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "spreadsheet-id")
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/url-id/edit",
    )

    assert get_rules_management_spreadsheet_id() == "spreadsheet-id"


def test_rules_workbook_extracts_env_workbook_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/url-id/edit#gid=0",
    )

    assert get_rules_management_spreadsheet_id() == "url-id"


def test_rules_workbook_resolves_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = DictConfig(
        {
            "rules": {
                "management_workbook_url": "https://docs.google.com/spreadsheets/d/config-url-id/edit",
            }
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "config-url-id"


def test_kafka_promote_consumer_imports_with_fake_kafka(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class FakeAIOKafkaConsumer:
        pass

    fake_aiokafka.AIOKafkaConsumer = FakeAIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    module = importlib.import_module("services.bus.kafka_consumer_promote")

    assert module.get_rules_management_spreadsheet_id is get_rules_management_spreadsheet_id
