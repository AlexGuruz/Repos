from __future__ import annotations

import json

from kylo import watcher_runtime


class _Cfg:
    def __init__(self):
        self.data = {
            "sheets": {"companies": [{"key": "JGD"}]},
            "posting": {"sheets": {"apply": True}},
            "runtime": {"circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30}},
        }

    def get(self, dotted_key, default=None):
        cur = self.data
        for part in str(dotted_key).split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def test_watcher_does_not_ack_checksums_after_partial_post_failure(monkeypatch, tmp_path):
    state_path = tmp_path / "watch_state.json"
    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(state_path))
    monkeypatch.setattr(watcher_runtime, "load_config", lambda: _Cfg())
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda _cid: "rules-v1")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda _cfg, _cid: "intake-v1")

    import services.posting.jgdtruth_poster as poster

    monkeypatch.setattr(poster, "run", lambda _cid, rules_changed=False: {"partial_failure": True})

    result = watcher_runtime.tick_once(["JGD"])

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert result["summaries"]["JGD"]["partial_failure"] is True
    assert state["seen"]["JGD"] == {"rules": "rules-v1", "intake": "intake-v1"}
    assert state.get("acked", {}).get("JGD") is None
    assert state["circuit_breaker"]["consecutive_failures"] == 1
