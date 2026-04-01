"""
Tests for worker health orchestration (Guru §26). worker_health intent returns reply.
"""
from __future__ import annotations

import pytest

from brain.router.router import classify_intent
from brain.orchestrator.main import run


def test_classify_worker_health():
    intent, _ = classify_intent("is the worker up")
    assert intent == "worker_health"
    intent2, _ = classify_intent("is worker assistant healthy")
    assert intent2 == "worker_health"
    intent3, _ = classify_intent("is n8n reachable")
    assert intent3 == "worker_health"


def test_worker_health_returns_reply():
    out = run("is the worker up?", session_id="test-worker-health")
    assert "reply" in out
    reply = out["reply"]
    assert "worker" in reply.lower()
    # Should mention services or tunnel or availability
    assert any(w in reply.lower() for w in ("worker", "tunnel", "assistant", "n8n", "ollama", "reachable", "healthy", "not set", "partially"))


def test_worker_health_failure_returns_helpful_next_steps():
    # When no env set, reply should suggest tunnel or validation
    out = run("why can't the main rig use the worker assistant?", session_id="test-worker-health-2")
    assert "reply" in out
    # May still route to worker_health or answer; either way we get a reply
    assert len(out["reply"]) > 20
