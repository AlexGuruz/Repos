from __future__ import annotations


class _Cfg:
    def __init__(self, data: dict):
        self.data = data

    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


def test_watcher_does_not_ack_checksum_when_posting_reports_error(monkeypatch):
    from kylo import watcher_runtime
    from services.posting import jgdtruth_poster

    saved_states: list[dict] = []
    cfg = _Cfg(
        {
            "runtime": {"mode": "post", "circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30}},
            "posting": {"sheets": {"apply": True}},
            "sheets": {"companies": [{"key": "NUGZ"}]},
        }
    )

    monkeypatch.setattr(watcher_runtime, "load_config", lambda: cfg)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher_runtime, "_load_state", lambda: {})
    monkeypatch.setattr(watcher_runtime, "_save_state", lambda state: saved_states.append(state))
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda _cid: "rules-1")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda _cfg, _cid: "intake-1")
    monkeypatch.setattr(
        jgdtruth_poster,
        "run",
        lambda _cid, rules_changed=False: {"cells_written": 0, "failed_range_count": 1, "error": True},
    )

    result = watcher_runtime.tick_once(["NUGZ"])

    assert result["posting_attempted"] is True
    assert result["summaries"]["NUGZ"]["error"] is True
    assert saved_states
    assert "NUGZ" not in (saved_states[-1].get("acked") or {})
    assert saved_states[-1]["circuit_breaker"]["consecutive_failures"] == 1
