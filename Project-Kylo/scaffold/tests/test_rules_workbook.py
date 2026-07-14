from __future__ import annotations

from services.common.rules_workbook import get_rules_management_spreadsheet_id
from services.posting.jgdtruth_poster import _post_success_key


def test_rules_management_spreadsheet_id_prefers_explicit_config(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")

    cfg = {
        "rules": {
            "management_spreadsheet_id": "config-sheet",
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/url-sheet/edit",
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "config-sheet"


def test_rules_management_spreadsheet_id_resolves_url_and_env(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/url-sheet/edit#gid=0"}}

    assert get_rules_management_spreadsheet_id(cfg) == "url-sheet"

    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")
    assert get_rules_management_spreadsheet_id({}) == "env-sheet"


def test_post_success_key_keeps_same_target_rows_distinct() -> None:
    first = _post_success_key("sid", "TRANSACTIONS", 4, "'JGD'!B10")
    second = _post_success_key("sid", "TRANSACTIONS", 5, "'JGD'!B10")

    assert first != second
