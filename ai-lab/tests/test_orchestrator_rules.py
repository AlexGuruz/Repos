"""
Tests for orchestrator runtime loading of Guru workflow_rules.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Conftest adds ai-lab root to path
from brain.orchestrator.main import run, _load_workflow_rules


def test_load_workflow_rules_missing_file():
    with patch("brain.orchestrator.main._root", Path("/nonexistent")):
        rules = _load_workflow_rules()
    assert rules == []


def test_load_workflow_rules_with_rr(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "workflow_rules.json").write_text(
        json.dumps([
            {"mode": "RR", "scope": "global", "summary": "Always cite sources."},
            {"mode": "PR", "scope": "global", "summary": "Preview first."},
        ]),
        encoding="utf-8",
    )
    with patch("brain.orchestrator.main._root", tmp_path):
        rules = _load_workflow_rules()
    assert len(rules) == 2
    rr = [r for r in rules if r.get("mode") == "RR"]
    assert len(rr) == 1
    assert "cite sources" in rr[0].get("summary", "")


def test_run_answer_includes_rr_rules_when_present(tmp_path):
    """When RR rules are loaded, the default-answer fallback includes them (Guru §24)."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "workflow_rules.json").write_text(
        json.dumps([{"mode": "RR", "scope": "global", "summary": "Cite sources."}]),
        encoding="utf-8",
    )
    # Non-greeting message so we skip the "Ready. Active topic" early return
    # Mock grounded response so we reach the fallback path where rr_context is appended
    # Mock no LLM so reply is the fallback (which includes RR rules)
    fake_grounded = {
        "evidence_block": "",
        "proposals_suffix": "",
        "proposals": [],
        "answer_style": "direct_status",
        "routing_reason": "test",
    }
    with patch("brain.orchestrator.main._root", tmp_path), \
         patch("brain.orchestrator.main.build_grounded_response", return_value=fake_grounded), \
         patch("brain.orchestrator.main.chat_completion", return_value=None):
        result = run("What is the status of things?")
    assert "reply" in result
    assert "Active RR rules" in result["reply"]
    assert "Cite sources" in result["reply"]
