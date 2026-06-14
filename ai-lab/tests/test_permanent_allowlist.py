from __future__ import annotations

import pytest

from brain import permanent_allowlist as allowlist


def test_permanent_rule_matches_exact_scoped_payload(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    rule = allowlist.add_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "detail": "ignored if not present later"},
    )

    assert rule["id"].startswith("PAR-")
    assert allowlist.find_matching_rule(
        "run_approved",
        {"script_path": "registry/foo.py", "detail": "ignored if not present later"},
    )["id"] == rule["id"]
    assert allowlist.find_matching_rule("run_approved", {"script_path": "registry/bar.py"}) is None


def test_permanent_rules_reject_blank_and_never_permanent_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))

    with pytest.raises(ValueError):
        allowlist.add_rule("run_approved", {})
    with pytest.raises(ValueError):
        allowlist.add_rule("restart_service", {"path": "backend"})
