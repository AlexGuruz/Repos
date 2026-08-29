from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, values: dict[str, str]):
        self.values = values

    def get(self, dotted: str, default=None):
        return self.values.get(dotted, default)


def test_rules_management_spreadsheet_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "envSpreadsheetId1234567890")

    assert get_rules_management_spreadsheet_id(_Cfg({"rules.management_spreadsheet_id": "cfgSpreadsheetId123"})) == "envSpreadsheetId1234567890"


def test_rules_management_spreadsheet_id_from_config_id(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    assert get_rules_management_spreadsheet_id(_Cfg({"rules.management_spreadsheet_id": "cfgSpreadsheetId1234567890"})) == "cfgSpreadsheetId1234567890"


def test_rules_management_spreadsheet_id_from_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = _Cfg(
        {
            "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/urlSpreadsheetId1234567890/edit"
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "urlSpreadsheetId1234567890"
