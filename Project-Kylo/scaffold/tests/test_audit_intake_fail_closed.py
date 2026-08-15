import pytest

from services.audit import intake_loader
from services.audit.tick import run_audit_tick


class DictConfig:
    def __init__(self, data):
        self.data = data

    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def _cfg():
    return DictConfig(
        {
            "sheets": {
                "companies": [
                    {
                        "key": "NUGZ",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/test-spreadsheet/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
        }
    )


def test_load_intake_for_company_raises_on_configured_tab_failure(monkeypatch):
    def fake_download(spreadsheet_id, service_account, sheet_name_override=None):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary sheet API failure")
        return "initials,date,company,description,amount\nAB,01/01/2025,NUGZ,Test transaction,100.00\n"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)

    with pytest.raises(RuntimeError, match="refusing partial audit snapshot"):
        intake_loader.load_intake_for_company(_cfg(), "NUGZ")


def test_run_audit_tick_does_not_save_registry_after_intake_failure(monkeypatch):
    def fail_load_all_intake(cfg, companies):
        raise RuntimeError("NUGZ test-spreadsheet BANK: temporary sheet API failure")

    def fail_if_saved(*args, **kwargs):
        raise AssertionError("registry should not be saved after partial intake failure")

    monkeypatch.setattr("services.audit.tick.load_all_intake", fail_load_all_intake)
    monkeypatch.setattr("services.audit.tick.save_row_registry", fail_if_saved)
    monkeypatch.setattr("services.audit.tick.save_tick_snapshot", fail_if_saved)

    summary = run_audit_tick(_cfg(), ["NUGZ"], instance_id="TEST")

    assert summary["error"].startswith("intake_load_failed:")
