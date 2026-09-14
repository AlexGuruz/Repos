from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """
version: 1
runtime:
  dry_run: false
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: secrets/service_account.json
sheets:
  companies: []
rules:
  management_workbook_url: https://docs.google.com/spreadsheets/d/from-config-id/edit
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {}
posting:
  sheets:
    apply: true
""".lstrip(),
        encoding="utf-8",
    )


class _Cfg:
    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def get(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)


def test_extract_spreadsheet_id_accepts_url_and_raw_id() -> None:
    from services.common.rules_workbook import extract_spreadsheet_id

    assert (
        extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0")
        == "abc123"
    )
    assert extract_spreadsheet_id("raw-sheet-id") == "raw-sheet-id"
    assert extract_spreadsheet_id(None) == ""


def test_rules_management_id_prefers_env(monkeypatch) -> None:
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_SPREADSHEET_ID",
        "https://docs.google.com/spreadsheets/d/env-id/edit",
    )

    assert (
        get_rules_management_spreadsheet_id(
            _Cfg({"rules.management_spreadsheet_id": "cfg-id"})
        )
        == "env-id"
    )


def test_rules_management_id_uses_config_url(monkeypatch) -> None:
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    assert (
        get_rules_management_spreadsheet_id(
            _Cfg(
                {
                    "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg-url-id/edit"
                }
            )
        )
        == "cfg-url-id"
    )


def test_promote_consumer_imports_with_rules_workbook_helper(
    monkeypatch, tmp_path: Path
) -> None:
    _write_config(tmp_path / "config" / "kylo.config.yaml")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_SHEETS_POST", raising=False)

    aiokafka = types.ModuleType("aiokafka")

    class AIOKafkaConsumer:
        pass

    aiokafka.AIOKafkaConsumer = AIOKafkaConsumer
    monkeypatch.setitem(sys.modules, "aiokafka", aiokafka)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    module = importlib.import_module("services.bus.kafka_consumer_promote")

    assert module.DO_POST is True
    assert module.get_rules_management_spreadsheet_id(module._cfg) == "from-config-id"
