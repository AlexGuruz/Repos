from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


def test_rules_workbook_prefers_configured_spreadsheet_id(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-id")
    cfg = {
        "rules": {
            "management_spreadsheet_id": "config-id",
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/url-id/edit",
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "config-id"


def test_rules_workbook_extracts_id_from_configured_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/url-id/edit#gid=0"}}

    assert get_rules_management_spreadsheet_id(cfg) == "url-id"


def test_rules_workbook_falls_back_to_env(monkeypatch) -> None:
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_SPREADSHEET_ID",
        "https://docs.google.com/spreadsheets/d/env-id/edit",
    )

    assert get_rules_management_spreadsheet_id({}) == "env-id"
