"""
Tests for brain.router.router classify_intent.
"""
from __future__ import annotations

import pytest

from brain.router.router import classify_intent


def test_classify_answer():
    intent, params = classify_intent("Hello")
    assert intent == "answer"
    assert params == {}


def test_classify_run_script():
    intent, params = classify_intent("run script backup")
    assert intent == "run"
    assert params == {}


def test_classify_sales_today():
    intent, params = classify_intent("sales today growflow")
    assert intent == "run"
    assert params.get("tool_hint") == "growflow_sales_today"
    assert params.get("args", {}).get("date") == "today"


def test_classify_sales_today_fluid_phrasing():
    """Short/slang phrasing still triggers growflow sales."""
    for phrase in ("whats my growflow sales for today", "my sales today", "growflow sales"):
        intent, params = classify_intent(phrase)
        assert intent == "run", f"Expected run for: {phrase!r}"
        assert params.get("tool_hint") == "growflow_sales_today", phrase


def test_classify_approval():
    intent, _ = classify_intent("approve abc-123")
    assert intent == "approval"
    intent, _ = classify_intent("deny xyz")
    assert intent == "approval"


def test_classify_scan_repo_default():
    intent, params = classify_intent("scan repo")
    assert intent == "run_agent"
    assert params.get("agent") == "repo_cartographer"
    assert params.get("repo_name") == "repos_root"


def test_classify_scan_repo_with_name():
    intent, params = classify_intent("scan repo ai-lab")
    assert intent == "run_agent"
    assert params.get("agent") == "repo_cartographer"
    assert params.get("repo_name") == "ai-lab"


def test_classify_summarize_repo_with_name():
    intent, params = classify_intent("summarize repo my-project")
    assert intent == "run_agent"
    assert params.get("agent") == "repo_cartographer"
    assert params.get("repo_name") == "my-project"


def test_classify_scan_repo_case_insensitive():
    intent, params = classify_intent("SCAN REPO geomapper")
    assert intent == "run_agent"
    assert params.get("repo_name") == "geomapper"


def test_classify_find_in_repos_fluid_phrasing():
    """Find/search in repos -> repo_search; look in repo -> run_agent (scan)."""
    for phrase in ("find it in repos", "search repos"):
        intent, params = classify_intent(phrase)
        assert intent == "repo_search", f"Expected repo_search for: {phrase!r}"
    intent, params = classify_intent("look in repo")
    assert intent == "run_agent"
    assert params.get("agent") == "repo_cartographer"


def test_classify_scan_results():
    """Show/view scan results and follow-up summary phrases."""
    for phrase in ("show scan results", "view scan results", "what did the scan tell you", "improvements from the scan"):
        intent, params = classify_intent(phrase)
        assert intent == "scan_results", f"Expected scan_results for: {phrase!r}"


def test_classify_execute_proposal():
    """'Do it', 'yes', 'go ahead' -> execute_proposal."""
    for phrase in ("do it", "yes", "go ahead", "do that"):
        intent, _ = classify_intent(phrase)
        assert intent == "execute_proposal", phrase


def test_classify_repo_search_with_query():
    """'Search repos for X' -> repo_search with query."""
    intent, params = classify_intent("search repos for growflow")
    assert intent == "repo_search"
    assert params.get("query") == "growflow"


def test_classify_hardware_status():
    """Guru §25: hardware/GPU/CPU/lagging questions -> hardware_status."""
    for phrase in (
        "what's my hardware doing right now",
        "why is my system lagging",
        "what's using my gpu memory",
        "how much cpu headroom do i have",
        "keep the main rig responsive while ai runs",
    ):
        intent, _ = classify_intent(phrase)
        assert intent == "hardware_status", f"Expected hardware_status for: {phrase!r}"


def test_classify_empty_and_whitespace():
    intent, params = classify_intent("")
    assert intent == "answer"
    intent, params = classify_intent("   ")
    assert intent == "answer"


def test_classify_repo_status_and_agenda_as_answer():
    for phrase in (
        "summarize current repo status",
        "current repo status",
        "open project agenda",
        "what changed recently?",
    ):
        intent, _ = classify_intent(phrase)
        assert intent == "answer", phrase


def test_classify_worker_index():
    """Worker Assistant: index repo on worker (Guru §26)."""
    intent, params = classify_intent("index repo")
    assert intent == "worker_index"
    assert params.get("repo_path") in (None, "repos_root") or isinstance(params.get("repo_path"), str)
    intent, params = classify_intent("index repos for ai-lab")
    assert intent == "worker_index"


def test_classify_worker_retrieve():
    """Worker Assistant: query/retrieve from worker."""
    intent, params = classify_intent("query worker for summary")
    assert intent == "worker_retrieve"
    intent, params = classify_intent("ask worker assistant")
    assert intent == "worker_retrieve"


def test_classify_trigger_workflow():
    """n8n trigger: trigger workflow / run n8n (approval-gated)."""
    intent, params = classify_intent("trigger workflow my-flow")
    assert intent == "trigger_workflow"
    assert params.get("workflow_id") in ("my-flow", "default") or params.get("workflow_id")
    intent, params = classify_intent("run n8n workflow")
    assert intent == "trigger_workflow"
