from __future__ import annotations

import pytest

from brain import permanent_allowlist as allowlist


def test_add_and_find_scoped_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "rules.json")

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "repo_id": "ai-lab"},
        note="test",
        source_approval_id="approval-1",
    )

    found = allowlist.find_matching_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "repo_id": "ai-lab", "reason": "extra"},
    )
    assert found is not None
    assert found["id"] == rule["id"]

    assert allowlist.find_matching_rule(
        "run_approved",
        {"script_path": "registry/other.py", "repo_id": "ai-lab"},
    ) is None


def test_rejects_unscoped_or_never_permanent_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "rules.json")

    with pytest.raises(ValueError, match="scoped"):
        allowlist.add_rule("run_approved", {})

    with pytest.raises(ValueError, match="cannot be permanently"):
        allowlist.add_rule("restart_service", {"target": "backend"})


def test_brain_spec_match_payload_flattens_safe_nested_fields():
    payload = allowlist.brain_spec_match_payload(
        {
            "action_type": "run_approved",
            "payload": {"script_path": "registry/foo.py", "ignored": "x"},
            "supervisor_payload": {"target": "backend"},
        }
    )

    assert payload == {
        "target": "backend",
        "script_path": "registry/foo.py",
        "action_type": "run_approved",
    }
