from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_workbook_resolves_nested_config_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU/edit"
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "1VA76RvF5Q6gmgIrAbLby1zQltUNEpdf-fvW8qSLw5wU"


def test_rules_workbook_env_spreadsheet_id_wins(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-id-1234567890")
    cfg = {"rules": {"management_spreadsheet_id": "config-sheet-id-1234567890"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet-id-1234567890"
