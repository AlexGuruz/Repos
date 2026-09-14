from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_rules_management_spreadsheet_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-id")
    cfg = _Cfg({"rules.management_spreadsheet_id": "cfg-sheet-id"})

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet-id"


def test_rules_management_spreadsheet_id_extracts_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = _Cfg(
        {
            "rules.management_workbook_url": (
                "https://docs.google.com/spreadsheets/d/sheet-from-url/edit#gid=0"
            )
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "sheet-from-url"


def test_rules_management_spreadsheet_id_supports_plain_dict(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_spreadsheet_id": "dict-sheet-id"}}

    assert get_rules_management_spreadsheet_id(cfg) == "dict-sheet-id"
