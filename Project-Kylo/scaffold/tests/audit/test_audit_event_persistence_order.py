from __future__ import annotations

from pathlib import Path

import pytest

from services.audit import tick


class _FakeRecord:
    row_key = "row-new"


class _FakeEvent:
    row_key = "row-old"
    event = "AMOUNT_REVISION"
    changed_field = "amount_cents"
    before = "100"
    after = "200"
    anomalies: list[str] = []

    def human_line(self, instance_id: str) -> str:
        return f"{instance_id}: amount changed"


def _patch_audit_tick(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    reg_path = tmp_path / "row_registry.json"
    bl_path = tmp_path / "business_line_registry.json"
    order: list[str] = []

    monkeypatch.setattr(tick, "row_registry_path", lambda _instance_id: reg_path)
    monkeypatch.setattr(tick, "business_line_registry_path", lambda _instance_id: bl_path)
    monkeypatch.setattr(tick, "audit_log_path", lambda _instance_id: tmp_path / "audit.log")
    monkeypatch.setattr(tick, "audit_jsonl_path", lambda _instance_id: tmp_path / "audit.jsonl")
    monkeypatch.setattr(tick, "load_row_registry", lambda path: {"row-old": object()} if path == reg_path else {})
    monkeypatch.setattr(tick, "load_all_intake", lambda _cfg, _companies: ([{"row": 1}], {}))
    monkeypatch.setattr(tick.RowRecord, "from_txn", staticmethod(lambda _txn, first_seen_at: _FakeRecord()))
    monkeypatch.setattr(tick, "build_business_line_registry", lambda _rows: {})
    monkeypatch.setattr(tick, "diff_registries", lambda *args, **kwargs: [_FakeEvent()])
    monkeypatch.setattr(tick, "diff_business_line_registries", lambda *args, **kwargs: [])
    monkeypatch.setattr(tick, "detect_from_bank_payroll_pairs", lambda *args, **kwargs: [])
    monkeypatch.setattr(tick, "detect_kylo_posted_amount_variance", lambda *args, **kwargs: [])
    monkeypatch.setattr(tick, "merge_registry", lambda *args, **kwargs: {"row-new": _FakeRecord()})
    monkeypatch.setattr(tick, "merge_business_line_registry", lambda *args, **kwargs: {})
    monkeypatch.setattr(tick, "save_row_registry", lambda *args, **kwargs: order.append("save"))
    monkeypatch.setattr(tick, "emit_audit_alerts", lambda *args, **kwargs: order.append("alert") or 0)
    monkeypatch.setattr(tick, "save_tick_snapshot", lambda *args, **kwargs: tmp_path / "snapshot")
    return order


def test_audit_log_failure_does_not_save_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    order = _patch_audit_tick(monkeypatch, tmp_path)

    def fail_log(*args, **kwargs):
        order.append("log")
        raise OSError("disk full")

    monkeypatch.setattr(tick, "append_audit_log", fail_log)
    monkeypatch.setattr(tick, "append_audit_jsonl", lambda *args, **kwargs: order.append("jsonl"))

    with pytest.raises(OSError):
        tick.run_audit_tick({}, ["JGD"], instance_id="JGD_2026")

    assert order == ["log"]


def test_audit_registry_saved_after_event_logs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    order = _patch_audit_tick(monkeypatch, tmp_path)
    monkeypatch.setattr(tick, "append_audit_log", lambda *args, **kwargs: order.append("log"))
    monkeypatch.setattr(tick, "append_audit_jsonl", lambda *args, **kwargs: order.append("jsonl"))

    tick.run_audit_tick({}, ["JGD"], instance_id="JGD_2026")

    assert order[:4] == ["log", "jsonl", "save", "save"]
    assert "alert" in order[4:]
