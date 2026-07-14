from __future__ import annotations

import pytest

from services.audit import intake_loader


class _EmptyProcessor:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def parse_transactions(self):
        return []


def test_load_intake_for_company_raises_on_tab_failure(monkeypatch) -> None:
    monkeypatch.setattr(intake_loader, "intake_urls_for_company", lambda *a, **k: ["sheet-url"])
    monkeypatch.setattr(intake_loader, "_extract_spreadsheet_id", lambda _url: "sheet123")
    monkeypatch.setattr(intake_loader, "PettyCashCSVProcessor", _EmptyProcessor)

    def _download(_sid, _sa, *, sheet_name_override):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary sheets failure")
        return "csv"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", _download)

    with pytest.raises(intake_loader.IntakeLoadError, match="BANK"):
        intake_loader.load_intake_for_company({}, "JGD")
