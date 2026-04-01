"""
Tests for brain.worker_health (Guru §26). Health checks never raise; return normalized shape.
"""
from __future__ import annotations

import pytest

from brain.worker_health import (
    check_worker_assistant,
    check_worker_n8n,
    check_worker_ollama,
    get_worker_health_snapshot,
    WorkerHealthSnapshot,
    ServiceHealth,
)


def test_check_worker_assistant_returns_service_health():
    s = check_worker_assistant("worker-rig-01")
    assert isinstance(s, ServiceHealth)
    assert s.name == "worker_assistant"
    assert isinstance(s.ok, bool)
    assert s.detail  # env not set or ok/error message


def test_check_worker_n8n_returns_service_health():
    s = check_worker_n8n("worker-rig-01")
    assert isinstance(s, ServiceHealth)
    assert s.name == "n8n"


def test_check_worker_ollama_returns_service_health():
    s = check_worker_ollama("worker-rig-01")
    assert isinstance(s, ServiceHealth)
    assert s.name == "ollama"


def test_get_worker_health_snapshot_returns_snapshot():
    snap = get_worker_health_snapshot("worker-rig-01")
    assert isinstance(snap, WorkerHealthSnapshot)
    assert snap.worker_name == "worker-rig-01"
    assert isinstance(snap.services, list)
    assert len(snap.services) == 3
    assert all(isinstance(s, ServiceHealth) for s in snap.services)
    assert isinstance(snap.all_ok, bool)
    assert isinstance(snap.ssh_configured, bool)


def test_health_checks_never_raise():
    """Health checks must not raise even when unreachable."""
    check_worker_assistant("worker-rig-01")
    check_worker_n8n("worker-rig-01")
    check_worker_ollama("worker-rig-01")
    get_worker_health_snapshot("worker-rig-01")
