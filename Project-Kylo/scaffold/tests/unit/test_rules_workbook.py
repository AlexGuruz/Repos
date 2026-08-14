from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def test_rules_management_id_from_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "spreadsheet-id")
    assert get_rules_management_spreadsheet_id(_Cfg({})) == "spreadsheet-id"


def test_rules_management_id_from_config_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = _Cfg(
        {
            "rules": {
                "management_workbook_url": "https://docs.google.com/spreadsheets/d/abc123DEF456/edit",
            }
        }
    )
    assert get_rules_management_spreadsheet_id(cfg) == "abc123DEF456"
