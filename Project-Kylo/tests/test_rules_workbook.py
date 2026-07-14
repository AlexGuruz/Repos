from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id, spreadsheet_id_from_url


def test_spreadsheet_id_from_google_sheets_url() -> None:
    assert (
        spreadsheet_id_from_url("https://docs.google.com/spreadsheets/d/abc_123-XYZ/edit#gid=0")
        == "abc_123-XYZ"
    )


def test_rules_management_spreadsheet_id_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-id")
    cfg = {"rules": {"management_spreadsheet_id": "cfg-sheet-id"}}
    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet-id"


def test_rules_management_spreadsheet_id_reads_nested_dict_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/url-sheet-id/edit"}}
    assert get_rules_management_spreadsheet_id(cfg) == "url-sheet-id"
