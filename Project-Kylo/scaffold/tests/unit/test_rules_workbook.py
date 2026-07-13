from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, dotted_key, default=None):
        cur = self.data
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def test_rules_workbook_uses_configured_spreadsheet_id(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    assert (
        get_rules_management_spreadsheet_id(_Cfg({"rules": {"management_spreadsheet_id": "sheet123"}}))
        == "sheet123"
    )


def test_rules_workbook_extracts_id_from_management_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = _Cfg(
        {
            "rules": {
                "management_workbook_url": "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit"
            }
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU"


def test_rules_workbook_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")

    assert get_rules_management_spreadsheet_id(_Cfg({"rules": {}})) == "env-sheet"
