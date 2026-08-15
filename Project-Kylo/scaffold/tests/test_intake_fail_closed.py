from __future__ import annotations

import pytest


class _Cfg:
    def __init__(self, data: dict):
        self.data = data

    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def _cfg() -> _Cfg:
    return _Cfg(
        {
            "google": {"service_account_json_path": "service-account.json"},
            "sheets": {
                "companies": [
                    {
                        "key": "NUGZ",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/source-sheet-id/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
        }
    )


def _csv_for(tab: str) -> str:
    return "\n".join(
        [
            "date,company,description,amount,unused,posted",
            f"2025-01-01,NUGZ,{tab} purchase,12.34,,FALSE",
        ]
    )


def test_audit_intake_aborts_on_partial_tab_load(monkeypatch):
    from services.audit import intake_loader

    def fake_download(_sid, _service_account, *, sheet_name_override=None):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary sheets failure")
        return _csv_for(str(sheet_name_override or "TRANSACTIONS"))

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)

    with pytest.raises(intake_loader.IntakeLoadError, match="BANK"):
        intake_loader.load_intake_for_company(_cfg(), "NUGZ")


def test_posting_aborts_on_partial_tab_load_before_rules(monkeypatch):
    from services.posting import jgdtruth_poster
    from services.state.store import State

    def fake_download(_sid, _service_account, *, sheet_name_override=None):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary sheets failure")
        return _csv_for(str(sheet_name_override or "TRANSACTIONS"))

    def fail_if_rules_loaded(_company):
        raise AssertionError("posting should abort before rule loading")

    monkeypatch.setattr(jgdtruth_poster, "load_config", lambda: _cfg())
    monkeypatch.setattr(jgdtruth_poster, "load_state", lambda: State())
    monkeypatch.setattr(jgdtruth_poster, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr(jgdtruth_poster, "fetch_rules_from_jgdtruth", fail_if_rules_loaded)

    with pytest.raises(RuntimeError, match="Incomplete intake load.*BANK"):
        jgdtruth_poster.run("NUGZ")
