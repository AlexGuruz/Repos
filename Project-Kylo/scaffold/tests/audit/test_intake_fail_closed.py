from __future__ import annotations

import pytest

from services.audit import intake_loader, tick
from services.audit.intake_loader import IntakeLoadError


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        cur = self.data
        for part in str(key).split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


class _Processor:
    def __init__(self, *_args, source_tab: str = "", **_kwargs):
        self.source_tab = source_tab

    def parse_transactions(self):
        if self.source_tab == "TRANSACTIONS":
            return iter(
                [
                    {
                        "company_id": "JGD",
                        "posted_date": "2026-01-01",
                        "amount_cents": 100,
                        "description": "Alpha",
                        "row_index_0based": 1,
                    }
                ]
            )
        return iter([])


def _cfg():
    return _Cfg(
        {
            "google": {"service_account_json_path": "sa.json"},
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/source-sheet/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
        }
    )


def test_intake_loader_raises_on_partial_tab_failure(monkeypatch):
    monkeypatch.setattr(intake_loader, "PettyCashCSVProcessor", _Processor)

    def fake_download(_sid, _sa, *, sheet_name_override=None):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary Sheets failure")
        return "csv"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)

    with pytest.raises(IntakeLoadError) as exc:
        intake_loader.load_intake_for_company(_cfg(), "JGD")

    assert "BANK" in str(exc.value)
    assert "temporary Sheets failure" in str(exc.value)


def test_audit_tick_does_not_persist_when_intake_fails(monkeypatch):
    writes = []

    def fail_load(*_args, **_kwargs):
        raise IntakeLoadError(["JGD:source-sheet:BANK: temporary Sheets failure"])

    monkeypatch.setattr(tick, "load_all_intake", fail_load)
    monkeypatch.setattr(tick, "save_row_registry", lambda *_args, **_kwargs: writes.append("registry"))
    monkeypatch.setattr(tick, "save_tick_snapshot", lambda *_args, **_kwargs: writes.append("snapshot"))

    summary = tick.run_audit_tick(_cfg(), ["JGD"], instance_id="TEST")

    assert summary["error"].startswith("intake_load_failed:")
    assert writes == []
