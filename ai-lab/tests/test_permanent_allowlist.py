from __future__ import annotations

import pytest

from brain import permanent_allowlist


def test_add_find_and_delete_permanent_rule(tmp_path, monkeypatch):
    rules_path = tmp_path / "approval_logs" / "permanent_allowlist.json"
    monkeypatch.setattr(permanent_allowlist, "_rules_path", rules_path)

    rule = permanent_allowlist.add_rule(
        "restart_service",
        {"service": "worker-assistant"},
        note="trusted service restart",
        source_approval_id="approval-1",
    )

    assert rule["id"].startswith("perm-")
    assert permanent_allowlist.list_rules()[0]["match"] == {"service": "worker-assistant"}
    assert permanent_allowlist.find_matching_rule(
        "restart_service",
        {"service": "worker-assistant", "detail": "ignored"},
    )["id"] == rule["id"]
    assert permanent_allowlist.find_matching_rule("restart_service", {"service": "other"}) is None
    assert permanent_allowlist.delete_rule(rule["id"]) is True
    assert permanent_allowlist.list_rules() == []


def test_add_rule_rejects_action_only_permanent_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(permanent_allowlist, "_rules_path", tmp_path / "rules.json")

    with pytest.raises(ValueError, match="match"):
        permanent_allowlist.add_rule("restart_service", {})


def test_brain_spec_match_payload_uses_nested_payload_and_path_alias():
    payload = permanent_allowlist.brain_spec_match_payload(
        {
            "action": "modify_registry",
            "payload": {"target": "registry/tool_registry.json", "detail": "ignored"},
        }
    )

    assert payload["target"] == "registry/tool_registry.json"
    assert payload["file_path"] == "registry/tool_registry.json"
    assert "detail" not in payload
