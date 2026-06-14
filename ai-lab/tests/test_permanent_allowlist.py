from __future__ import annotations

import importlib

import pytest

from brain import permanent_allowlist as allowlist


def test_orchestrator_imports_with_permanent_allowlist_module():
    module = importlib.import_module("brain.orchestrator.main")

    assert callable(module.run)


def test_add_rule_persists_and_matches_only_exact_scoped_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "permanent.json"))

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "detail": "run foo", "ignored": "x"},
        note="from test",
        source_approval_id="APR-1",
    )

    assert rule["id"].startswith("PAR-")
    assert allowlist.find_matching_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "detail": "run foo", "extra": "ignored"},
    )["id"] == rule["id"]
    assert allowlist.find_matching_rule(
        "run_approved",
        {"script_path": "registry/bar.py", "detail": "run foo"},
    ) is None
    assert allowlist.find_matching_rule(
        "write_sheet",
        {"script_path": "registry/foo.py", "detail": "run foo"},
    ) is None


def test_duplicate_rule_returns_existing_rule(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "permanent.json"))

    first = allowlist.add_rule("write_sheet", {"target": "JGDTruth!A1:B2"})
    second = allowlist.add_rule("write_sheet", {"target": "JGDTruth!A1:B2"})

    assert second["id"] == first["id"]
    assert len(allowlist.list_rules()) == 1


def test_rejects_unscoped_or_never_permanent_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "permanent.json"))

    with pytest.raises(ValueError, match="scoped field"):
        allowlist.add_rule("run_approved", {"detail": "too broad"})

    with pytest.raises(ValueError, match="cannot be made permanent"):
        allowlist.add_rule("restart_service", {"target": "backend"})

    assert allowlist.find_matching_rule("restart_service", {"target": "backend"}) is None


def test_brain_spec_match_payload_normalizes_approval_rows():
    payload = allowlist.brain_spec_match_payload(
        {
            "file_path": " registry/scripts.json ",
            "action": "manual_enqueue",
            "reason": "needs approval",
            "args": {"ignored": True},
        }
    )

    assert payload == {
        "file_path": "registry/scripts.json",
        "action_type": "manual_enqueue",
        "reason": "needs approval",
        "detail": "needs approval",
    }
