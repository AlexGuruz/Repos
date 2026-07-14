from __future__ import annotations


def test_extract_spreadsheet_id_from_google_sheets_url():
    from services.common.rules_workbook import extract_spreadsheet_id

    assert (
        extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123_DEF-456/edit#gid=0")
        == "abc123_DEF-456"
    )


def test_extract_spreadsheet_id_keeps_raw_id():
    from services.common.rules_workbook import extract_spreadsheet_id

    assert extract_spreadsheet_id("abc123_DEF-456") == "abc123_DEF-456"


def test_rules_management_spreadsheet_id_prefers_env(monkeypatch):
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env_sid")

    assert get_rules_management_spreadsheet_id(
        {"rules": {"management_spreadsheet_id": "cfg_sid"}}
    ) == "env_sid"


def test_rules_management_spreadsheet_id_reads_nested_dict(monkeypatch):
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    assert (
        get_rules_management_spreadsheet_id(
            {
                "rules": {
                    "management_workbook_url": (
                        "https://docs.google.com/spreadsheets/d/nested_sid/edit"
                    )
                }
            }
        )
        == "nested_sid"
    )


def test_rules_management_spreadsheet_id_reads_config_getter(monkeypatch):
    from services.common.rules_workbook import get_rules_management_spreadsheet_id

    class Cfg:
        def get(self, key, default=None):
            if key == "rules.management_spreadsheet_id":
                return "getter_sid"
            return default

    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    assert get_rules_management_spreadsheet_id(Cfg()) == "getter_sid"
