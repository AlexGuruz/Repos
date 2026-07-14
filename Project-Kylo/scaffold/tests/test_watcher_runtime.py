from __future__ import annotations

import json

from kylo import watcher_runtime


class _Config:
    def __init__(self, values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def test_sheets_dry_run_does_not_ack_pending_change(monkeypatch, tmp_path):
    state_path = tmp_path / "watch_state.json"
    state_path.write_text(
        json.dumps(
            {
                "seen": {"JGD": {"rules": "rules-old", "intake": "intake-old"}},
                "acked": {"JGD": {"rules": "rules-old", "intake": "intake-old"}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(state_path))
    monkeypatch.setattr(
        watcher_runtime,
        "load_config",
        lambda: _Config(
            {
                "posting.sheets.apply": True,
                "runtime.dry_run": False,
                "runtime.circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30},
            }
        ),
    )
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda cfg: False)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda company: "rules-new")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda cfg, company: "intake-new")
    monkeypatch.setenv("KYLO_SHEETS_DRY_RUN", "1")

    result = watcher_runtime.tick_once(["JGD"])

    assert result["posting_attempted"] is False
    assert result["posting_skipped_reason"] == "dry_run"
    assert result["sheets_dry_run"] is True

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["seen"]["JGD"] == {"rules": "rules-new", "intake": "intake-new"}
    assert saved["acked"]["JGD"] == {"rules": "rules-old", "intake": "intake-old"}
