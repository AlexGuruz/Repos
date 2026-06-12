from __future__ import annotations

from core.ai_lab import ensure_ai_lab_root_on_path

ensure_ai_lab_root_on_path()

from brain.permanent_allowlist import (  # noqa: E402
    add_rule,
    approval_payload_subset,
    delete_rule,
    find_matching_rule,
    list_rules,
)


def test_permanent_rule_matches_only_exact_scoped_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    rule = add_rule(
        "run_approved",
        {
            "script_path": "registry/safe_report.py",
            "detail": "ignored extra fields are allowed",
        },
        note="from approval-1",
    )

    assert rule["id"].startswith("perm-")
    assert find_matching_rule(
        "run_approved",
        {"script_path": "registry/safe_report.py", "detail": "ignored extra fields are allowed"},
    )["id"] == rule["id"]
    assert find_matching_rule("run_approved", {"script_path": "registry/other.py"}) is None
    assert find_matching_rule("write_sheet", {"script_path": "registry/safe_report.py"}) is None


def test_permanent_rules_reject_unscoped_and_forbidden_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    try:
        add_rule("run_approved", {})
    except ValueError as exc:
        assert "match" in str(exc)
    else:
        raise AssertionError("empty permanent match should fail closed")

    try:
        add_rule("restart_service", {"target": "worker"})
    except ValueError as exc:
        assert "cannot be permanently allowlisted" in str(exc)
    else:
        raise AssertionError("restart_service should never be permanent")

    assert find_matching_rule("restart_service", {"target": "worker"}) is None


def test_delete_rule_persists_removal(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    rule = add_rule("run_approved", {"tool_name": "sales_report"})

    assert len(list_rules()) == 1
    assert delete_rule(rule["id"]) is True
    assert list_rules() == []
    assert delete_rule(rule["id"]) is False


def test_approval_payload_subset_keeps_only_stable_non_empty_fields():
    assert approval_payload_subset(
        {
            "script_path": " registry/safe_report.py ",
            "unknown": "value",
            "target": "",
            "repo_id": None,
        }
    ) == {"script_path": "registry/safe_report.py"}
