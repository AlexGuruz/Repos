from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Config:
    def __init__(self, values: dict[str, object]) -> None:
        self._values = values

    def get(self, key: str, default: object = None) -> object:
        return self._values.get(key, default)


def test_rules_workbook_prefers_spreadsheet_id_env(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "sheet-id-env")
    monkeypatch.setenv(
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
        "https://docs.google.com/spreadsheets/d/sheet-id-url/edit",
    )

    assert get_rules_management_spreadsheet_id({"rules": {"management_spreadsheet_id": "sheet-id-config"}}) == "sheet-id-env"


def test_rules_workbook_extracts_workbook_url_from_dict_config(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/sheet-id-from-config/edit#gid=0"
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "sheet-id-from-config"


def test_rules_workbook_supports_config_object_getter(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)

    cfg = _Config({"rules.management_spreadsheet_id": "sheet-id-from-object"})

    assert get_rules_management_spreadsheet_id(cfg) == "sheet-id-from-object"
