from __future__ import annotations

import sys
import types

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_management_spreadsheet_id_prefers_env(monkeypatch):
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/env123456/edit#gid=0",
    )

    assert get_rules_management_spreadsheet_id({"rules": {"management_spreadsheet_id": "cfg123"}}) == "env123456"


def test_rules_management_spreadsheet_id_from_nested_config(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg987/edit"}}

    assert get_rules_management_spreadsheet_id(cfg) == "cfg987"


def test_kafka_consumer_promote_imports_without_real_aiokafka(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    fake_aiokafka = types.ModuleType("aiokafka")

    class AIOKafkaConsumer:  # pragma: no cover - only needed for import binding
        pass

    fake_aiokafka.AIOKafkaConsumer = AIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    __import__("services.bus.kafka_consumer_promote")
