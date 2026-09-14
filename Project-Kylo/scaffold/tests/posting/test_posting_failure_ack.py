from __future__ import annotations

import json


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


def test_watcher_does_not_ack_partial_posting_failure(monkeypatch, tmp_path):
    from kylo import watcher_runtime
    from services.posting import jgdtruth_poster

    cfg = DictConfig(
        {
            "runtime": {"mode": "post", "circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30}},
            "posting": {"sheets": {"apply": True}},
        }
    )
    watch_state = tmp_path / "watch_state.json"
    watch_state.write_text(
        json.dumps(
            {
                "seen": {"NUGZ": {"rules": "rules-1", "intake": "intake-old"}},
                "acked": {"NUGZ": {"rules": "rules-1", "intake": "intake-old"}},
                "circuit_breaker": {"paused_until": "", "consecutive_failures": 0},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(watch_state))
    monkeypatch.setattr(watcher_runtime, "load_config", lambda: cfg)
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda company: "rules-1")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda cfg, company: "intake-new")
    monkeypatch.setattr(
        jgdtruth_poster,
        "run",
        lambda company, rules_changed=False: {
            "posting_complete": False,
            "failed_ranges_count": 1,
            "cells_written": 0,
        },
    )

    result = watcher_runtime.tick_once(["NUGZ"])

    saved = json.loads(watch_state.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert saved["seen"]["NUGZ"] == {"rules": "rules-1", "intake": "intake-new"}
    assert saved["acked"]["NUGZ"] == {"rules": "rules-1", "intake": "intake-old"}
    assert saved["circuit_breaker"]["consecutive_failures"] == 1
