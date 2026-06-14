from __future__ import annotations

import pytest

from core.ai_lab import ensure_ai_lab_root_on_path

ensure_ai_lab_root_on_path()

from brain import permanent_allowlist  # noqa: E402


def test_permanent_rule_matches_only_scoped_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(permanent_allowlist, "_rules_path", tmp_path / "rules.json")

    rule = permanent_allowlist.add_rule("write_sheet", {"target": "sheet-1"})

    assert permanent_allowlist.find_matching_rule("write_sheet", {"target": "sheet-1"})["id"] == rule["id"]
    assert permanent_allowlist.find_matching_rule("write_sheet", {"target": "sheet-2"}) is None
    assert permanent_allowlist.find_matching_rule("run_approved", {"target": "sheet-1"}) is None


def test_permanent_rule_rejects_unscoped_or_dangerous_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(permanent_allowlist, "_rules_path", tmp_path / "rules.json")

    with pytest.raises(ValueError, match="at least one scoped match"):
        permanent_allowlist.add_rule("write_sheet", {"ignored": "not scoped"})

    with pytest.raises(ValueError, match="cannot be permanently allowlisted"):
        permanent_allowlist.add_rule("restart_service", {"target": "worker"})

    assert permanent_allowlist.find_matching_rule("restart_service", {"target": "worker"}) is None


def test_permanent_rules_fail_closed_when_storage_is_corrupt(tmp_path, monkeypatch):
    rules_path = tmp_path / "rules.json"
    rules_path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(permanent_allowlist, "_rules_path", rules_path)

    assert permanent_allowlist.list_rules() == []
    assert permanent_allowlist.find_matching_rule("write_sheet", {"target": "sheet-1"}) is None
