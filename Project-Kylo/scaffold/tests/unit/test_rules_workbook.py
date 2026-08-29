from __future__ import annotations

from services.common.rules_workbook import (
    extract_spreadsheet_id,
    get_rules_management_spreadsheet_id,
)


class _Cfg:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_extract_spreadsheet_id_from_url_and_raw_id():
    assert extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/sheet123/edit#gid=0") == "sheet123"
    assert extract_spreadsheet_id("sheet456") == "sheet456"
    assert extract_spreadsheet_id("") == ""


def test_rules_management_spreadsheet_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")
    cfg = _Cfg({"rules.management_spreadsheet_id": "cfg-sheet"})

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet"


def test_rules_management_spreadsheet_uses_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = _Cfg({"rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/url-sheet/edit"})

    assert get_rules_management_spreadsheet_id(cfg) == "url-sheet"
