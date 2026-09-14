import json
import sys
import types
from pathlib import Path

from kylo import watcher_runtime


class _Cfg:
    def __init__(self):
        self._values = {
            "posting.sheets.apply": True,
            "runtime.circuit_breaker": {
                "max_consecutive_failures": 5,
                "pause_minutes": 30,
            },
        }

    def get(self, key, default=None):
        return self._values.get(key, default)


def _prime_watcher(monkeypatch, tmp_path: Path, post_summary: dict) -> Path:
    state_path = tmp_path / "watch_state.json"
    state_path.write_text(
        json.dumps(
            {
                "seen": {"JGD": {"rules": "old-rules", "intake": "old-intake"}},
                "acked": {"JGD": {"rules": "old-rules", "intake": "old-intake"}},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(state_path))
    monkeypatch.setattr(watcher_runtime, "load_config", lambda: _Cfg())
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda _company: "new-rules")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda _cfg, _company: "new-intake")

    fake_poster = types.ModuleType("services.posting.jgdtruth_poster")
    fake_poster.run = lambda _company, *, rules_changed=False: post_summary
    monkeypatch.setitem(sys.modules, "services.posting.jgdtruth_poster", fake_poster)

    for name in (
        "KYLO_INSTANCE_ID",
        "KYLO_READ_ONLY",
        "KYLO_DISABLE_POSTING_FOR",
        "KYLO_DISABLE_POSTING_COMPANIES",
    ):
        monkeypatch.delenv(name, raising=False)

    return state_path


def test_watcher_does_not_ack_partial_post_failure(monkeypatch, tmp_path):
    state_path = _prime_watcher(
        monkeypatch,
        tmp_path,
        {"posting_complete": False, "failed_ranges_count": 1},
    )

    result = watcher_runtime.tick_once(["JGD"])

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert state["seen"]["JGD"] == {"rules": "new-rules", "intake": "new-intake"}
    assert state["acked"]["JGD"] == {"rules": "old-rules", "intake": "old-intake"}
    assert state["circuit_breaker"]["consecutive_failures"] == 1


def test_watcher_acks_complete_post(monkeypatch, tmp_path):
    state_path = _prime_watcher(
        monkeypatch,
        tmp_path,
        {"posting_complete": True, "failed_ranges_count": 0},
    )

    result = watcher_runtime.tick_once(["JGD"])

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert result["posting_attempted"] is True
    assert state["acked"]["JGD"] == {"rules": "new-rules", "intake": "new-intake"}
    assert state["circuit_breaker"]["consecutive_failures"] == 0
