from __future__ import annotations

import pytest

from core.ai_lab import ensure_ai_lab_root_on_path


ensure_ai_lab_root_on_path()
from brain import permanent_allowlist as allowlist  # noqa: E402


def test_permanent_rule_lifecycle_is_exact_and_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "rules.json")

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "ignored": "not persisted"},
        note="from test",
        source_approval_id="approval-1",
    )

    assert rule["id"].startswith("PAR-")
    assert rule["match"] == {"script_path": "registry/foo.py"}
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/foo.py"}) == rule
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/bar.py"}) is None

    duplicate = allowlist.add_rule("run_approved", {"script_path": "registry/foo.py"})
    assert duplicate["id"] == rule["id"]
    assert allowlist.delete_rule(rule["id"]) is True
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/foo.py"}) is None


def test_permanent_rule_rejects_unscoped_or_forbidden_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "rules.json")

    with pytest.raises(ValueError, match="at least one"):
        allowlist.add_rule("run_approved", {})

    with pytest.raises(ValueError, match="cannot be permanently allowlisted"):
        allowlist.add_rule("restart_service", {"target": "worker"})
