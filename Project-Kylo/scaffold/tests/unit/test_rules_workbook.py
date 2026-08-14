from __future__ import annotations

from dataclasses import dataclass

from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


@dataclass
class ConfigWithGet:
    values: dict[str, object]

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)


def test_extract_spreadsheet_id_from_google_url() -> None:
    url = "https://docs.google.com/spreadsheets/d/sheet_123ABC/edit#gid=0"
    assert extract_spreadsheet_id(url) == "sheet_123ABC"


def test_extract_spreadsheet_id_accepts_raw_id() -> None:
    assert extract_spreadsheet_id("sheet_123ABC") == "sheet_123ABC"
    assert extract_spreadsheet_id("sheet_123ABC?gid=0") == "sheet_123ABC"


def test_extract_spreadsheet_id_rejects_non_sheet_url() -> None:
    assert extract_spreadsheet_id("https://example.com/not-a-sheet") == ""


def test_rules_management_id_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env_sheet")
    cfg = {"rules": {"management_spreadsheet_id": "cfg_sheet"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env_sheet"


def test_rules_management_id_reads_dotted_config_object(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = ConfigWithGet(
        {
            "rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg_sheet/edit",
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "cfg_sheet"


def test_rules_management_id_reads_nested_config_dict(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = {"rules": {"management_spreadsheet_id": "nested_sheet"}}

    assert get_rules_management_spreadsheet_id(cfg) == "nested_sheet"
