from __future__ import annotations

import pytest

from brain import permanent_allowlist as allowlist


def test_add_find_and_delete_scoped_rule(tmp_path, monkeypatch):
    rules_path = tmp_path / "rules.json"
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(rules_path))

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "ignored": "nope"},
        note="repeat safe script",
        source_approval_id="approval-1",
    )

    assert rule["id"].startswith("PAR-")
    assert rule["match"] == {"script_path": "registry/foo.py"}
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/foo.py"}) == rule
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/bar.py"}) is None
    assert allowlist.add_rule("run_approved", {"script_path": "registry/foo.py"}) == rule
    assert allowlist.delete_rule(rule["id"]) is True
    assert allowlist.list_rules() == []


def test_never_permanent_actions_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    with pytest.raises(ValueError, match="cannot be permanently allowlisted"):
        allowlist.add_rule("restart_service", {"target": "backend"})


def test_brain_spec_match_payload_flattens_nested_payload():
    payload = allowlist.brain_spec_match_payload(
        {
            "action": "run_approved",
            "payload": {"script_path": "registry/foo.py", "secret": "ignored"},
            "reason": "rerun known script",
        }
    )

    assert payload == {
        "script_path": "registry/foo.py",
        "action_type": "run_approved",
        "reason": "rerun known script",
    }
