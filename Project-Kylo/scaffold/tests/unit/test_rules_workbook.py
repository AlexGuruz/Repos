from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


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


def test_rules_management_spreadsheet_id_loads_default_config(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    monkeypatch.delenv("KYLO_INSTANCE_ID", raising=False)
    monkeypatch.delenv("KYLO_CONFIG_PATH", raising=False)
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "config" / "kylo.config.yaml",
        """
version: 1
runtime:
  dry_run: true
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: C:\\\\secrets\\\\sa.json
sheets:
  companies: []
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {}
rules:
  management_workbook_url: https://docs.google.com/spreadsheets/d/default-config-id/edit
posting:
  sheets:
    apply: false
""".lstrip(),
    )

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id() == "default-config-id"


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
