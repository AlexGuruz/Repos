from __future__ import annotations

import pytest

from services.common.rules_workbook import get_rules_management_spreadsheet_id
from services.audit import intake_loader


def test_rules_management_spreadsheet_id_from_url() -> None:
    cfg = {
        "rules": {
            "management_workbook_url": "https://docs.google.com/spreadsheets/d/abc123XYZ/edit#gid=0",
        }
    }

    assert get_rules_management_spreadsheet_id(cfg) == "abc123XYZ"


def test_rules_management_spreadsheet_id_env_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "envSid")
    cfg = {"rules": {"management_spreadsheet_id": "cfgSid"}}

    assert get_rules_management_spreadsheet_id(cfg) == "envSid"


def test_audit_intake_fails_closed_on_partial_tab_load(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyProcessor:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def parse_transactions(self):
            return []

    def fake_download(sid: str, sa: str, *, sheet_name_override: str):
        if sheet_name_override == "BANK":
            raise RuntimeError("rate limited")
        return ""

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr(intake_loader, "PettyCashCSVProcessor", DummyProcessor)

    cfg = {
        "sheets": {
            "companies": [{"key": "JGD", "workbook_url": "https://docs.google.com/spreadsheets/d/sid/edit"}]
        }
    }

    with pytest.raises(intake_loader.IntakeLoadError, match="partial intake load blocked"):
        intake_loader.load_intake_for_company(cfg, "JGD")
