from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_workbook_accepts_nested_dict_config(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_spreadsheet_id": "1abcDEF_234567890123456789"}}
    assert get_rules_management_spreadsheet_id(cfg) == "1abcDEF_234567890123456789"


def test_rules_workbook_extracts_id_from_url(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {
        "rules": {
            "management_workbook_url": (
                "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit"
            )
        }
    }
    assert get_rules_management_spreadsheet_id(cfg) == "1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU"
