from __future__ import annotations

from pathlib import Path

from services.audit.row_model import RowRecord
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


def _row(row0: int, description: str, amount_cents: int, *, posted_amount_cents=None) -> RowRecord:
    return RowRecord(
        row_key=f"sid|TRANSACTIONS|{row0}",
        source_spreadsheet_id="sid",
        source_tab="TRANSACTIONS",
        row_index_0based=row0,
        company_id="NUGZ",
        posted_date="2026-01-01",
        description=description,
        amount_cents=amount_cents,
        posted_flag=True,
        first_seen_at="2026-01-01T00:00:00Z",
        content_fp=f"fp-{row0}",
        txn_uid=f"txn-{row0}",
        business_line_uid=f"bl-{row0}",
        kylo_posted_amount_cents=posted_amount_cents,
    )


def test_audit_detectors_do_not_refire_for_unchanged_prior_anomalies(monkeypatch):
    prior_rows = [
        _row(10, "FROM BANK", 50000),
        _row(11, "PAYROLL 12345", -50000),
        _row(20, "edited amount", 10000, posted_amount_cents=7500),
    ]
    prior = {row.row_key: row for row in prior_rows}
    txns = [
        {
            "source_spreadsheet_id": row.source_spreadsheet_id,
            "source_tab": row.source_tab,
            "row_index_0based": row.row_index_0based,
            "company_id": row.company_id,
            "posted_date": row.posted_date,
            "description": row.description,
            "amount_cents": row.amount_cents,
            "posted_flag": row.posted_flag,
            "txn_uid": row.txn_uid,
            "business_line_uid": row.business_line_uid,
            "kylo_posted_amount_cents": row.kylo_posted_amount_cents,
        }
        for row in prior_rows
    ]

    cfg = DictConfig(
        {
            "runtime": {"mode": "audit"},
            "audit": {"write_notes": True, "apply_highlights": True, "pair_rules": {"enabled": True}},
        }
    )

    monkeypatch.setattr("services.audit.tick.load_all_intake", lambda cfg, companies: (txns, {}))
    monkeypatch.setattr(
        "services.audit.tick.load_row_registry",
        lambda path: {row.business_line_uid: row for row in prior_rows}
        if Path(path).name == "business_line_registry.json"
        else prior,
    )
    monkeypatch.setattr("services.audit.tick.save_row_registry", lambda *args, **kwargs: None)
    monkeypatch.setattr("services.audit.tick.save_tick_snapshot", lambda *args, **kwargs: Path("snapshot"))
    monkeypatch.setattr("services.audit.tick.emit_audit_alerts", lambda *args, **kwargs: 0)

    summary = run_audit_tick(cfg, ["NUGZ"], instance_id="TEST")

    assert summary["events"] == 0
