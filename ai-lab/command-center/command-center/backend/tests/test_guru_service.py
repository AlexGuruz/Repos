from __future__ import annotations

import json

import pytest

from services import guru_service


@pytest.fixture
def guru_tmp(monkeypatch, tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "policy").mkdir()
    (tmp_path / "logs" / "guru_threads").mkdir(parents=True)
    (tmp_path / "logs" / "config_changes").mkdir(parents=True)
    monkeypatch.setattr(guru_service, "AI_LAB_ROOT", tmp_path)
    monkeypatch.setattr(guru_service, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(guru_service, "POLICY_DIR", tmp_path / "policy")
    monkeypatch.setattr(guru_service, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(guru_service, "THREAD_DIR", tmp_path / "logs" / "guru_threads")
    monkeypatch.setattr(guru_service, "AUDIT_DIR", tmp_path / "logs" / "config_changes")
    return tmp_path


def test_rr_message_saves_preferences_workflow_rule_and_audit(guru_tmp):
    result = guru_service.submit_mode_message(
        "RR",
        "Include source references, mention file paths, and keep answers detailed.",
    )

    prefs = json.loads((guru_tmp / "memory" / "preferences.json").read_text(encoding="utf-8"))
    rules = json.loads((guru_tmp / "memory" / "workflow_rules.json").read_text(encoding="utf-8"))
    audit_files = list((guru_tmp / "logs" / "config_changes").glob("*_RR.json"))

    assert result["saved"] is True
    assert prefs["include_source_references_in_code_discussions"] is True
    assert prefs["mention_relevant_files_when_relevant"] is True
    assert prefs["default_response_verbosity"] == "detailed"
    assert rules[0]["mode"] == "RR"
    assert "include source references" in rules[0]["summary"]
    assert len(audit_files) == 1


def test_atl_requires_confirm_then_writes_trust_rules(guru_tmp):
    pending = guru_service.submit_mode_message("ATL", "Auto-allow health checks and repo scans to summaries.")
    assert pending["saved"] is False
    assert pending["current_draft"]["draft"]["mode"] == "ATL"

    confirmed = guru_service.confirm_mode("ATL")
    trust_rules = json.loads((guru_tmp / "memory" / "trust_rules.json").read_text(encoding="utf-8"))

    assert confirmed["saved"] is True
    assert confirmed["current_draft"] is None
    task_classes = {rule["task_class"] for rule in trust_rules}
    assert "health_check" in task_classes
    assert "repo_scan_to_summaries" in task_classes


def test_revert_last_restores_previous_rr_state(guru_tmp):
    guru_service.submit_mode_message("RR", "Include source references and mention file paths.")
    reverted = guru_service.revert_last("RR")

    prefs_text = (guru_tmp / "memory" / "preferences.json").read_text(encoding="utf-8")
    audit_files = list((guru_tmp / "logs" / "config_changes").glob("*_RR.json"))
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))

    assert reverted["saved"] is True
    assert "include_source_references" not in prefs_text
    assert audit["reverted"] is True
    assert audit["reverted_at"]


def test_confirm_mode_raises_without_pending_draft(guru_tmp):
    with pytest.raises(ValueError, match="No pending draft"):
        guru_service.confirm_mode("ATL")
