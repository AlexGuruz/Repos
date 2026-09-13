from __future__ import annotations

import importlib
import sys
import types

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_management_spreadsheet_id_resolves_from_env_url(monkeypatch):
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/abc123DEF456ghi789JKL012/edit",
    )

    assert get_rules_management_spreadsheet_id() == "abc123DEF456ghi789JKL012"


def test_kafka_consumer_promote_imports_with_fake_aiokafka(monkeypatch):
    fake_aiokafka = types.ModuleType("aiokafka")

    class AIOKafkaConsumer:  # pragma: no cover - import smoke only
        pass

    fake_aiokafka.AIOKafkaConsumer = AIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", fake_aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert mod.load_config is not None
    assert mod.get_rules_management_spreadsheet_id is get_rules_management_spreadsheet_id
