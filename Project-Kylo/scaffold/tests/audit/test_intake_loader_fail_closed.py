from __future__ import annotations

import pytest

from services.audit import intake_loader


class DottedConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_intake_loader_raises_on_tab_download_failure(monkeypatch):
    cfg = DottedConfig(
        {
            "google.service_account_json_path": "service-account.json",
            "intake.csv_processor.header_rows": 1,
        }
    )

    monkeypatch.setattr(intake_loader, "intake_urls_for_company", lambda _cfg, _company: ["spreadsheet-id"])

    def fake_download(_sid, _sa, *, sheet_name_override):
        if sheet_name_override == "BANK":
            raise TimeoutError("temporary sheets timeout")
        return "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)

    with pytest.raises(RuntimeError, match=r"failed to load intake tab spreadsheet-id\|BANK"):
        intake_loader.load_intake_for_company(cfg, "NUGZ")
