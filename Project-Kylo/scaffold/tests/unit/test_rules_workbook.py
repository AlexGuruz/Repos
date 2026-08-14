from __future__ import annotations

from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


def test_extract_spreadsheet_id_accepts_url_or_id():
    assert extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0") == "abc123"
    assert extract_spreadsheet_id("plain-id-123") == "plain-id-123"
    assert extract_spreadsheet_id("https://example.com/not-a-sheet") == ""


def test_get_rules_management_spreadsheet_id_prefers_env(monkeypatch):
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-id")
    cfg = {"rules": {"management_spreadsheet_id": "cfg-id"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env-id"


def test_get_rules_management_spreadsheet_id_reads_nested_config(monkeypatch):
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_WORKBOOK_URL", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg-url-id/edit"}}

    assert get_rules_management_spreadsheet_id(cfg) == "cfg-url-id"
