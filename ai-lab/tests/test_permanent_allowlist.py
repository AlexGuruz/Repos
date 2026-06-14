from __future__ import annotations

import importlib

import pytest

from brain import permanent_allowlist as allowlist


def _use_tmp_rules(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))


def test_orchestrator_imports_with_permanent_allowlist_present():
    orchestrator = importlib.import_module("brain.orchestrator.main")

    assert callable(orchestrator.run)


def test_add_find_and_delete_scoped_rule(monkeypatch, tmp_path):
    _use_tmp_rules(monkeypatch, tmp_path)

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "secret": "ignored"},
        note="from test",
        source_approval_id="APR-1",
    )

    assert rule["id"].startswith("PAR-")
    assert rule["match"] == {"script_path": "registry/foo.py"}
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/foo.py"})["id"] == rule["id"]
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/bar.py"}) is None
    assert allowlist.delete_rule(rule["id"]) is True
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/foo.py"}) is None


def test_rejects_unscoped_or_never_permanent_actions(monkeypatch, tmp_path):
    _use_tmp_rules(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="require at least one scope key"):
        allowlist.add_rule("run_approved", {"reason": "looks similar"})

    with pytest.raises(ValueError, match="cannot be permanently allowlisted"):
        allowlist.add_rule("restart_service", {"target": "command-center"})


def test_payload_helpers_strip_unknown_and_empty_fields():
    payload = allowlist.approval_payload_subset(
        {
            "repo_id": "ai-lab",
            "target": " ",
            "script_path": "tools/run.py",
            "password": "secret",
        }
    )

    assert payload == {"repo_id": "ai-lab", "script_path": "tools/run.py"}
