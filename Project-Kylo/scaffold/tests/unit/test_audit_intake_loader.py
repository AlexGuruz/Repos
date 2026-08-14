from __future__ import annotations

import pytest

from services.audit import intake_loader


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def test_partial_intake_tab_failure_raises(monkeypatch):
    cfg = _Cfg(
        {
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/source123/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
        }
    )

    def fake_download(spreadsheet_id, service_account, sheet_name_override=None):
        if sheet_name_override == "BANK":
            raise RuntimeError("transient sheets error")
        return "Date,Company,Description,Amount,Unused,Processed\n2026-01-02,JGD,Fuel,12.34,,FALSE\n"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)

    with pytest.raises(intake_loader.IntakeLoadIncomplete) as exc:
        intake_loader.load_intake_for_company(cfg, "JGD")

    assert "BANK" in str(exc.value)
    assert "transient sheets error" in str(exc.value)
