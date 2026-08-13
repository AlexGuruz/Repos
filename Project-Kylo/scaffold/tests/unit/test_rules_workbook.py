from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _minimal_config(spreadsheet_id: str) -> str:
    return f"""
version: 1
runtime:
  dry_run: false
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: /tmp/service_account.json
sheets:
  companies: []
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {{}}
posting:
  sheets:
    apply: true
rules:
  source: jgdtruth
  management_spreadsheet_id: {spreadsheet_id}
""".lstrip()


def test_rules_management_spreadsheet_id_resolves_from_config(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config" / "kylo.config.yaml"
    _write(config_path, _minimal_config("rules-sheet-123"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    from services.common.config_loader import load_config
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id(load_config()) == "rules-sheet-123"


def test_rules_management_spreadsheet_id_env_override_extracts_url(monkeypatch):
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_SPREADSHEET_ID",
        "https://docs.google.com/spreadsheets/d/env-sheet-456/edit",
    )

    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    assert get_rules_management_spreadsheet_id(None) == "env-sheet-456"


def test_promote_consumer_loads_yaml_config_for_posting(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "config" / "kylo.config.yaml"
    _write(config_path, _minimal_config("rules-sheet-789"))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("KYLO_SHEETS_POST", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    aiokafka = types.ModuleType("aiokafka")
    aiokafka.AIOKafkaConsumer = object
    monkeypatch.setitem(sys.modules, "aiokafka", aiokafka)

    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.connect = lambda *args, **kwargs: None
    psycopg2_extras = types.ModuleType("psycopg2.extras")
    psycopg2_extras.RealDictCursor = object
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", psycopg2_extras)

    rules_promoter_service = types.ModuleType("services.rules_promoter.service")
    rules_promoter_service.promote = lambda *args, **kwargs: {}
    monkeypatch.setitem(sys.modules, "services.rules_promoter.service", rules_promoter_service)

    replay_worker = types.ModuleType("services.replay.worker")
    replay_worker.replay_after_promotion = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "services.replay.worker", replay_worker)

    poster = types.ModuleType("services.sheets.poster")
    poster._get_service = lambda: None
    poster.ensure_company_tabs = lambda *args, **kwargs: {}
    poster._fetch_meta = lambda *args, **kwargs: ({}, [])
    poster.build_tab_name = lambda company_id, suffix: f"{company_id} {suffix}"
    monkeypatch.setitem(sys.modules, "services.sheets.poster", poster)

    sys.modules.pop("services.bus.kafka_consumer_promote", None)
    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert mod.DO_POST is True
    assert mod.get_rules_management_spreadsheet_id(mod._cfg) == "rules-sheet-789"
