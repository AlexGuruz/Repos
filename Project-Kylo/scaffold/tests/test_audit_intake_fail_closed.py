import pytest


class FakeCfg:
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


class FakeProcessor:
    def __init__(self, csv_content, *, header_rows, source_tab, source_spreadsheet_id):
        self.source_tab = source_tab
        self.source_spreadsheet_id = source_spreadsheet_id

    def parse_transactions(self):
        return [
            {
                "company_id": "JGD",
                "row_index_0based": 20,
                "posted_date": "2026-07-13",
                "description": f"{self.source_tab} row",
                "amount_cents": 1234,
            }
        ]


def test_load_intake_raises_on_partial_tab_download_failure(monkeypatch):
    from services.audit import intake_loader

    cfg = FakeCfg(
        {
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/sheet123/edit",
                    }
                ]
            },
            "google": {"service_account_json_path": "/tmp/no-live-google.json"},
        }
    )

    def fake_download(spreadsheet_id, service_account, *, sheet_name_override):
        if sheet_name_override == "BANK":
            raise RuntimeError("temporary sheet API failure")
        return "csv"

    monkeypatch.setattr(intake_loader, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr(intake_loader, "PettyCashCSVProcessor", FakeProcessor)

    with pytest.raises(intake_loader.IntakeLoadError) as exc:
        intake_loader.load_intake_for_company(cfg, "JGD")

    message = str(exc.value)
    assert "sheet123|BANK" in message
    assert "temporary sheet API failure" in message


def test_audit_tick_preserves_registry_when_intake_load_fails(monkeypatch, tmp_path):
    from services.audit import tick
    from services.audit.intake_loader import IntakeLoadError
    from services.audit.paths import business_line_registry_path, row_registry_path
    from services.audit.row_model import RowRecord
    from services.audit.snapshot import load_row_registry, save_row_registry

    instance_id = "JGD_TEST"
    previous = RowRecord(
        row_key="sheet123|BANK|20",
        source_spreadsheet_id="sheet123",
        source_tab="BANK",
        row_index_0based=20,
        company_id="JGD",
        posted_date="2026-07-13",
        description="baseline bank row",
        amount_cents=1234,
        first_seen_at="2026-07-13T00:00:00Z",
        business_line_uid="sheet123|BANK|JGD|2026-07-13|BASELINE BANK ROW",
    )

    monkeypatch.chdir(tmp_path)
    save_row_registry(row_registry_path(instance_id), {previous.row_key: previous})
    save_row_registry(business_line_registry_path(instance_id), {previous.business_line_uid: previous})

    monkeypatch.setattr(
        tick,
        "load_all_intake",
        lambda cfg, companies: (_ for _ in ()).throw(IntakeLoadError("incomplete intake load")),
    )

    summary = tick.run_audit_tick(
        FakeCfg({"audit": {"write_notes": False, "apply_highlights": False}}),
        ["JGD"],
        instance_id=instance_id,
    )

    assert summary["error"] == "intake_load_failed: incomplete intake load"
    assert summary["snapshot_dir"] == ""
    assert list(load_row_registry(row_registry_path(instance_id))) == [previous.row_key]
    assert list(load_row_registry(business_line_registry_path(instance_id))) == [previous.business_line_uid]
