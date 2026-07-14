from __future__ import annotations

from types import SimpleNamespace

from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


def test_extract_spreadsheet_id_from_google_sheets_url() -> None:
    assert (
        extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123_DEF-456/edit#gid=0")
        == "abc123_DEF-456"
    )


def test_get_rules_management_spreadsheet_id_prefers_env(monkeypatch) -> None:
    cfg = {"rules": {"management_spreadsheet_id": "from-config"}}
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "from-env")

    assert get_rules_management_spreadsheet_id(cfg) == "from-env"


def test_get_rules_management_spreadsheet_id_from_config_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/sheet-id-789/edit",
        }.get(key, default)
    )

    assert get_rules_management_spreadsheet_id(cfg) == "sheet-id-789"
