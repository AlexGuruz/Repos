from __future__ import annotations

import json
import sys
import types


class DotConfig(dict):
    def get(self, key, default=None):
        if isinstance(key, str) and "." in key:
            cur = self
            for part in key.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur
        return super().get(key, default)


class FakePostingState:
    def __init__(self):
        self.cell_signatures = {}

    def clear_skipped(self, _company):
        return None


def test_watcher_does_not_ack_partial_target_write_failure(tmp_path, monkeypatch):
    from kylo import watcher_runtime as wr

    watch_state = tmp_path / "watch_state.json"
    monkeypatch.setattr(wr, "WATCH_STATE_PATH", str(watch_state))
    monkeypatch.setattr(
        wr,
        "load_config",
        lambda: DotConfig(
            {
                "posting": {"sheets": {"apply": True}},
                "runtime": {"circuit_breaker": {"max_consecutive_failures": 5, "pause_minutes": 30}},
            }
        ),
    )
    monkeypatch.setattr(wr, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(wr, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(wr, "rules_checksum", lambda _company: "rules-v1")
    monkeypatch.setattr(wr, "intake_checksum", lambda _cfg, _company: "intake-v1")
    monkeypatch.delenv("KYLO_READ_ONLY", raising=False)
    monkeypatch.delenv("KYLO_DISABLE_POSTING_FOR", raising=False)
    monkeypatch.delenv("KYLO_DISABLE_POSTING_COMPANIES", raising=False)

    poster_mod = types.ModuleType("services.posting.jgdtruth_poster")
    poster_mod.run = lambda company, rules_changed=False: {
        "company": company,
        "partial_failure": True,
        "failed_ranges_count": 1,
        "failed_ranges": ["Target!B2"],
    }
    monkeypatch.setitem(sys.modules, "services.posting.jgdtruth_poster", poster_mod)

    state_mod = types.ModuleType("services.state.store")
    state_mod.StateError = RuntimeError
    state_mod.load_state = lambda: FakePostingState()
    state_mod.save_state = lambda _state: None
    monkeypatch.setitem(sys.modules, "services.state.store", state_mod)

    result = wr.tick_once(["NUGZ"])

    saved = json.loads(watch_state.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert result["summaries"]["NUGZ"]["partial_failure"] is True
    assert saved["seen"]["NUGZ"] == {"rules": "rules-v1", "intake": "intake-v1"}
    assert saved.get("acked", {}).get("NUGZ") is None
    assert saved["circuit_breaker"]["consecutive_failures"] == 1


def test_watcher_ack_helper_accepts_existing_success_summaries():
    from kylo.watcher_runtime import _posting_summary_failed

    assert _posting_summary_failed({"cells_written": 1, "failed_ranges_count": 0}) is False
    assert _posting_summary_failed({"failed_ranges": []}) is False
    assert _posting_summary_failed({"error": True}) is True
    assert _posting_summary_failed({"failed_ranges_count": 2}) is True
    assert _posting_summary_failed({"partial_failure": True}) is True
