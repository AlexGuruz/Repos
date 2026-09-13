from __future__ import annotations

import importlib
import sys
import types

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, values):
        self._values = values

    def get(self, dotted, default=None):
        return self._values.get(dotted, default)


def test_rules_management_spreadsheet_id_prefers_env_id(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "abc123DEF456ghi789JKL012")
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/other123DEF456ghi789JKL/edit",
    )

    assert get_rules_management_spreadsheet_id(_Cfg({})) == "abc123DEF456ghi789JKL012"


def test_rules_management_spreadsheet_id_resolves_from_env_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/abc123DEF456ghi789JKL012/edit",
    )

    assert get_rules_management_spreadsheet_id(_Cfg({})) == "abc123DEF456ghi789JKL012"


def test_rules_management_spreadsheet_id_resolves_from_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = _Cfg(
        {
            "rules.management_workbook_url": (
                "https://docs.google.com/spreadsheets/d/cfg123DEF456ghi789JKL012/edit"
            )
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "cfg123DEF456ghi789JKL012"


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
