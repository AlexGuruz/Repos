"""Unit tests for session reference resolution (PDR Phase 2.75)."""
import pytest
from brain.orchestrator.session_resolution import resolve_session_references, SessionResolution


def test_resolve_do_it_to_pending_proposal():
    session = {"pending_proposal": {"action": "repo_search", "query": "growflow"}, "active_topic": None}
    r = resolve_session_references("do it", session)
    assert r.resolved_reference == "pending_proposal"
    assert r.resolved_proposal == {"action": "repo_search", "query": "growflow"}
    assert r.confidence > 0.9


def test_resolve_that_scan_to_artifact():
    session = {
        "last_artifacts": [{"type": "repo_scan", "path": "/x/summary.md", "summary_path": "/x/summary.md"}],
        "active_topic": None,
    }
    r = resolve_session_references("what did that scan tell you", session)
    assert r.resolved_reference == "last_scan_artifact"
    assert r.resolved_artifact is not None
    assert r.resolved_artifact.get("type") == "repo_scan"


def test_resolve_why_did_that_fail():
    session = {"last_failure": {"intent": "growflow_sales", "reason": "path not found"}, "active_topic": None}
    r = resolve_session_references("why did that fail", session)
    assert r.resolved_reference == "last_failure"
    assert r.resolved_failure is not None


def test_empty_message():
    r = resolve_session_references("", {"active_topic": None})
    assert r.resolved_reference is None
    assert r.confidence == 0.0
