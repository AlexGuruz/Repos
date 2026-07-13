from services.common.rules_workbook import get_rules_management_spreadsheet_id


class _Config:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_rules_workbook_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet-id")

    assert get_rules_management_spreadsheet_id(_Config({"rules.management_spreadsheet_id": "cfg-id"})) == "env-sheet-id"


def test_rules_workbook_reads_configured_id(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)

    assert get_rules_management_spreadsheet_id(_Config({"rules.management_spreadsheet_id": "cfg-id"})) == "cfg-id"


def test_rules_workbook_extracts_id_from_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = _Config({"rules.management_workbook_url": "https://docs.google.com/spreadsheets/d/sheet_123-abc/edit"})

    assert get_rules_management_spreadsheet_id(cfg) == "sheet_123-abc"
