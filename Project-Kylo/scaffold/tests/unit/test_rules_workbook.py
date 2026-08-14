from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, data: dict):
        self.data = data

    def get(self, dotted_key: str, default=None):
        cur = self.data
        for part in dotted_key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def test_rules_management_spreadsheet_id_prefers_env_id(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "sheet-id-from-env")
    cfg = _Cfg({"rules": {"management_spreadsheet_id": "sheet-id-from-config"}})

    assert get_rules_management_spreadsheet_id(cfg) == "sheet-id-from-env"


def test_rules_management_spreadsheet_id_extracts_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = _Cfg(
        {
            "rules": {
                "management_workbook_url": "https://docs.google.com/spreadsheets/d/abc123XYZ/edit#gid=0"
            }
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "abc123XYZ"


def _install_import_stubs(monkeypatch):
    aiokafka = types.ModuleType("aiokafka")
    aiokafka.AIOKafkaConsumer = object
    monkeypatch.setitem(sys.modules, "aiokafka", aiokafka)

    psycopg2 = types.ModuleType("psycopg2")
    psycopg2.connect = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2)

    psycopg2_extras = types.ModuleType("psycopg2.extras")
    psycopg2_extras.RealDictCursor = object
    psycopg2_extras.execute_values = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "psycopg2.extras", psycopg2_extras)

    google = types.ModuleType("google")
    google_oauth2 = types.ModuleType("google.oauth2")
    google_sa = types.ModuleType("google.oauth2.service_account")

    class _Credentials:
        @staticmethod
        def from_service_account_file(*args, **kwargs):
            return object()

    google_sa.Credentials = _Credentials
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.oauth2", google_oauth2)
    monkeypatch.setitem(sys.modules, "google.oauth2.service_account", google_sa)

    googleapiclient = types.ModuleType("googleapiclient")
    google_discovery = types.ModuleType("googleapiclient.discovery")
    google_discovery.build = lambda *args, **kwargs: object()
    monkeypatch.setitem(sys.modules, "googleapiclient", googleapiclient)
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", google_discovery)


def test_kafka_promote_consumer_imports_and_honors_yaml_posting_apply(monkeypatch, tmp_path):
    _install_import_stubs(monkeypatch)
    cfg = tmp_path / "kylo.config.yaml"
    cfg.write_text(
        "\n".join(
            [
                "version: 1",
                "runtime:",
                "  mode: post",
                "google:",
                "  service_account_json_path: /tmp/service-account.json",
                "database:",
                "  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global",
                "sheets:",
                "  companies: []",
                "posting:",
                "  sheets:",
                "    apply: true",
                "rules:",
                "  management_spreadsheet_id: rules-sheet-id",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KYLO_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("KYLO_ENV_PATH", str(tmp_path / "missing.env"))
    monkeypatch.delenv("KYLO_SHEETS_POST", raising=False)
    sys.modules.pop("services.bus.kafka_consumer_promote", None)

    mod = importlib.import_module("services.bus.kafka_consumer_promote")

    assert mod._cfg is not None
    assert mod.DO_POST is True
    assert mod.get_rules_management_spreadsheet_id(mod._cfg) == "rules-sheet-id"
