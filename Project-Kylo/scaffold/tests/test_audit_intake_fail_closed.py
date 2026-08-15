from __future__ import annotations

from services.audit.paths import row_registry_path
from services.audit.row_model import RowRecord, make_business_line_uid
from services.audit.snapshot import load_row_registry, save_row_registry
from services.audit.tick import run_audit_tick


class _Cfg:
    def __init__(self) -> None:
        self.data = {
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/intake_sid/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
            "audit": {"write_notes": False, "apply_highlights": False},
        }

    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def test_audit_tick_does_not_overwrite_registry_after_partial_tab_failure(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    instance_id = "JGD_2026"
    previous = RowRecord(
        row_key="intake_sid|BANK|1",
        source_spreadsheet_id="intake_sid",
        source_tab="BANK",
        row_index_0based=1,
        company_id="JGD",
        posted_date="2026-01-02",
        description="Payroll",
        amount_cents=12345,
        first_seen_at="2026-01-02T00:00:00Z",
        txn_uid="txn-bank-1",
        business_line_uid=make_business_line_uid("intake_sid", "BANK", "JGD", "2026-01-02", "Payroll"),
        kylo_posted_at="2026-01-03T00:00:00Z",
        kylo_posted_amount_cents=12345,
    )
    save_row_registry(row_registry_path(instance_id), {previous.row_key: previous})

    def fake_download(spreadsheet_id, service_account_path, *, sheet_name_override=None, **_kwargs):
        if sheet_name_override == "BANK":
            raise RuntimeError("transient sheets failure")
        return "date,company,description,amount,unused,processed\n2026-01-02,JGD,Coffee,10.00,,\n"

    monkeypatch.setattr("services.audit.intake_loader.download_petty_cash_csv", fake_download)

    summary = run_audit_tick(_Cfg(), ["JGD"], instance_id=instance_id)

    assert summary["error"].startswith("intake_load_failed:")
    assert load_row_registry(row_registry_path(instance_id)) == {previous.row_key: previous}
