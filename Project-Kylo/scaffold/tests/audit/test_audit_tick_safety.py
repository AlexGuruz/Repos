from __future__ import annotations

import json
from pathlib import Path

from services.audit.row_model import RowRecord
from services.audit.snapshot import load_row_registry, save_row_registry
from services.audit.tick import run_audit_tick


class FakeCfg:
    def __init__(self):
        self.values = {
            "runtime.mode": "audit",
            "audit": {"enabled": True},
            "sheets.companies": [
                {
                    "key": "NUGZ",
                    "workbook_url": "https://docs.google.com/spreadsheets/d/test-spreadsheet-id",
                }
            ],
        }

    def get(self, key, default=None):
        return self.values.get(key, default)


def test_incomplete_audit_intake_does_not_overwrite_registry(monkeypatch, tmp_path: Path):
    reg_path = tmp_path / "row_registry.json"
    bl_path = tmp_path / "business_line_registry.json"
    previous = RowRecord(
        row_key="test-spreadsheet-id|TRANSACTIONS|20",
        source_spreadsheet_id="test-spreadsheet-id",
        source_tab="TRANSACTIONS",
        row_index_0based=20,
        company_id="NUGZ",
        posted_date="2026-07-10",
        description="Existing row",
        amount_cents=1234,
        first_seen_at="2026-07-10T00:00:00Z",
    )
    save_row_registry(reg_path, {previous.row_key: previous})
    save_row_registry(bl_path, {})

    monkeypatch.setattr("services.audit.tick.row_registry_path", lambda _instance_id: reg_path)
    monkeypatch.setattr("services.audit.tick.business_line_registry_path", lambda _instance_id: bl_path)
    monkeypatch.setattr(
        "services.audit.tick.load_all_intake",
        lambda _cfg, _companies: (
            [
                {
                    "source_spreadsheet_id": "test-spreadsheet-id",
                    "source_tab": "TRANSACTIONS",
                    "row_index_0based": 20,
                    "company_id": "NUGZ",
                    "posted_date": "2026-07-10",
                    "description": "Existing row",
                    "amount_cents": 1234,
                }
            ],
            {"test-spreadsheet-id|TRANSACTIONS": "csv"},
        ),
    )

    summary = run_audit_tick(FakeCfg(), ["NUGZ"], instance_id="test")

    assert summary["error"] == "intake_incomplete"
    assert summary["missing_csv_tabs"] == ["test-spreadsheet-id|BANK"]
    persisted = load_row_registry(reg_path)
    assert list(persisted) == [previous.row_key]
    assert json.loads(reg_path.read_text(encoding="utf-8"))[previous.row_key]["description"] == "Existing row"
