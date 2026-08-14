from __future__ import annotations


class _Cfg:
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


def test_watcher_does_not_ack_partial_post_failure(monkeypatch):
    import kylo.watcher_runtime as watcher
    from services.posting import jgdtruth_poster

    cfg = _Cfg(
        {
            "posting": {"sheets": {"apply": True}},
            "runtime": {"circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30}},
        }
    )
    saved_states = []

    monkeypatch.setattr(watcher, "load_config", lambda: cfg)
    monkeypatch.setattr(watcher, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher, "rules_checksum", lambda company: "rules-v1")
    monkeypatch.setattr(watcher, "intake_checksum", lambda _cfg, company: "intake-v1")
    monkeypatch.setattr(watcher, "_load_state", lambda: {})
    monkeypatch.setattr(watcher, "_save_state", lambda state: saved_states.append(state))
    monkeypatch.setattr(
        jgdtruth_poster,
        "run",
        lambda company, rules_changed=False: {"ok": False, "failed_ranges": ["'JGD EXPENSES'!B20"]},
    )

    result = watcher.tick_once(["JGD"])

    assert result["posting_attempted"] is True
    assert saved_states
    assert "JGD" not in (saved_states[-1].get("acked") or {})
    assert saved_states[-1]["circuit_breaker"]["consecutive_failures"] == 1
