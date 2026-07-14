from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from kylo import watcher_runtime


class FakeCfg:
    def get(self, key, default=None):
        values = {
            "runtime.mode": "post",
            "runtime.circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30},
            "posting.sheets.apply": True,
        }
        return values.get(key, default)


def test_partial_posting_failure_does_not_ack_changed_checksums(monkeypatch, tmp_path: Path):
    state_path = tmp_path / "watch_state.json"
    state_path.write_text(
        json.dumps(
            {
                "seen": {"NUGZ": {"rules": "r1", "intake": "old-intake"}},
                "acked": {"NUGZ": {"rules": "r1", "intake": "old-intake"}},
            }
        ),
        encoding="utf-8",
    )

    fake_poster = types.ModuleType("services.posting.jgdtruth_poster")
    fake_poster.run = lambda _cid, rules_changed=False: {
        "cells_written": 1,
        "failed_ranges": ["Sheet1!A1"],
        "partial_failure": True,
    }
    fake_state = types.ModuleType("services.state.store")
    fake_state.StateError = RuntimeError
    fake_state.load_state = lambda: None
    fake_state.save_state = lambda _state: None
    monkeypatch.setitem(sys.modules, "services.posting.jgdtruth_poster", fake_poster)
    monkeypatch.setitem(sys.modules, "services.state.store", fake_state)

    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(state_path))
    monkeypatch.setattr(watcher_runtime, "load_config", lambda: FakeCfg())
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda _cid: "r1")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda _cfg, _cid: "new-intake")
    monkeypatch.setenv("KYLO_ALLOW_POST", "1")
    monkeypatch.setenv("KYLO_RUNTIME_MODE", "post")

    result = watcher_runtime.tick_once(["NUGZ"])

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert watcher_runtime._posting_summary_failed(result["summaries"]["NUGZ"]) is True
    assert saved["seen"]["NUGZ"]["intake"] == "new-intake"
    assert saved["acked"]["NUGZ"]["intake"] == "old-intake"
    assert saved["circuit_breaker"]["consecutive_failures"] == 1
