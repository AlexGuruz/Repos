from __future__ import annotations

from pathlib import Path

from services.audit.row_model import RowRecord, content_fingerprint, make_business_line_uid, make_row_key
from services.audit.snapshot import load_row_registry, save_row_registry


def _record(*, sid: str, tab: str, row0: int, company: str = "JGD") -> RowRecord:
    posted_date = "2026-01-02"
    description = f"{tab} vendor {row0}"
    amount_cents = 1234 + row0
    business_line_uid = make_business_line_uid(sid, tab, company, posted_date, description)
    return RowRecord(
        row_key=make_row_key(sid, tab, row0),
        source_spreadsheet_id=sid,
        source_tab=tab,
        row_index_0based=row0,
        company_id=company,
        posted_date=posted_date,
        description=description,
        amount_cents=amount_cents,
        posted_flag=False,
        first_seen_at="2026-01-01T00:00:00Z",
        content_fp=content_fingerprint(posted_date, company, description, amount_cents),
        txn_uid=f"txn-{tab}-{row0}",
        business_line_uid=business_line_uid,
    )


def test_audit_tick_preserves_unloaded_tab_registry(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_READ_ONLY", "1")

    from services.audit.paths import business_line_registry_path, row_registry_path
    from services.audit.tick import run_audit_tick

    instance_id = "JGD_2026"
    sid = "spreadsheet-1"
    transactions_row = _record(sid=sid, tab="TRANSACTIONS", row0=1)
    bank_row = _record(sid=sid, tab="BANK", row0=2)
    previous_rows = {
        transactions_row.row_key: transactions_row,
        bank_row.row_key: bank_row,
    }
    save_row_registry(row_registry_path(instance_id), previous_rows)
    save_row_registry(
        business_line_registry_path(instance_id),
        {
            transactions_row.business_line_uid: transactions_row,
            bank_row.business_line_uid: bank_row,
        },
    )

    def fake_load_all_intake(cfg, companies):
        txn = transactions_row.to_dict()
        return [txn], {f"{sid}|TRANSACTIONS": "csv loaded"}

    monkeypatch.setattr("services.audit.tick.load_all_intake", fake_load_all_intake)
    monkeypatch.setattr("services.audit.tick.emit_audit_alerts", lambda *args, **kwargs: 0)

    summary = run_audit_tick({}, ["JGD"], instance_id=instance_id)

    assert summary["events"] == 0
    assert "error" not in summary
    saved = load_row_registry(row_registry_path(instance_id))
    assert set(saved) == {transactions_row.row_key, bank_row.row_key}
    assert saved[bank_row.row_key].description == bank_row.description


def test_audit_tick_still_removes_rows_from_loaded_tabs(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_READ_ONLY", "1")

    from services.audit.paths import business_line_registry_path, row_registry_path
    from services.audit.tick import run_audit_tick

    instance_id = "JGD_2026"
    sid = "spreadsheet-lowercase-id"
    kept_row = _record(sid=sid, tab="TRANSACTIONS", row0=1)
    removed_row = _record(sid=sid, tab="TRANSACTIONS", row0=2)
    unloaded_bank_row = _record(sid=sid, tab="BANK", row0=3)
    previous_rows = {
        kept_row.row_key: kept_row,
        removed_row.row_key: removed_row,
        unloaded_bank_row.row_key: unloaded_bank_row,
    }
    save_row_registry(row_registry_path(instance_id), previous_rows)
    save_row_registry(
        business_line_registry_path(instance_id),
        {row.business_line_uid: row for row in previous_rows.values()},
    )

    def fake_load_all_intake(cfg, companies):
        return [kept_row.to_dict()], {f"{sid}|transactions": "csv loaded"}

    monkeypatch.setattr("services.audit.tick.load_all_intake", fake_load_all_intake)
    monkeypatch.setattr("services.audit.tick.emit_audit_alerts", lambda *args, **kwargs: 0)

    summary = run_audit_tick({}, ["JGD"], instance_id=instance_id)

    assert summary["events"] == 1
    saved = load_row_registry(row_registry_path(instance_id))
    assert kept_row.row_key in saved
    assert removed_row.row_key not in saved
    assert unloaded_bank_row.row_key in saved
