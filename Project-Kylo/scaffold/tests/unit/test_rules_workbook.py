from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class DummyConfig:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values

    def get(self, dotted_key: str, default: object = None) -> object:
        return self.values.get(dotted_key, default)


def test_rules_workbook_extracts_id_from_management_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = DummyConfig(
        {
            "rules.management_workbook_url": (
                "https://docs.google.com/spreadsheets/d/1abcDEF_234567890-ghijkLMnopQRSTuv/edit"
            )
        }
    )

    assert get_rules_management_spreadsheet_id(cfg) == "1abcDEF_234567890-ghijkLMnopQRSTuv"


def test_rules_workbook_prefers_environment_override(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "1envSpreadsheetId_234567890")
    cfg = DummyConfig({"rules.management_spreadsheet_id": "1configSpreadsheetId_234567890"})

    assert get_rules_management_spreadsheet_id(cfg) == "1envSpreadsheetId_234567890"
