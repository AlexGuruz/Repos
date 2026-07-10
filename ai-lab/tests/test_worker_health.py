"""
Tests for brain.worker_health (Guru §26). Health checks never raise; return normalized shape.
"""
from __future__ import annotations

import time
import pytest

from brain.worker_health import (
    check_worker_assistant,
    check_worker_n8n,
    check_worker_ollama,
    get_last_known_worker_status,
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


def test_interactive_worker_health_timeout_budget_under_2_5s(monkeypatch):
    """Interactive checks enforce a 2s wall-clock budget even when probes hang."""
    from brain import worker_health as wh

    def _slow_service(name: str) -> ServiceHealth:
        time.sleep(5.0)
        return ServiceHealth(
            name=name,
            ok=False,
            url=None,
            status_code=None,
            detail="slow",
            latency_ms=None,
        )

    monkeypatch.setattr(wh, "check_worker_assistant", lambda *a, **k: _slow_service("worker_assistant"))
    monkeypatch.setattr(wh, "check_worker_n8n", lambda *a, **k: _slow_service("n8n"))
    monkeypatch.setattr(wh, "check_worker_ollama", lambda *a, **k: _slow_service("ollama"))

    t0 = time.perf_counter()
    snap = get_worker_health_snapshot("worker-rig-01", timeout_budget_ms=2000, interactive=True)
    elapsed = time.perf_counter() - t0

    assert elapsed < 2.5, f"interactive worker health exceeded budget: {elapsed:.3f}s"
    assert snap.worker_status == "offline_or_unreachable"
    assert snap.timeout_budget_ms == 2000
    assert snap.checked_at
    assert len(snap.services) == 3
    assert any("timeout" in s.detail.lower() or not s.ok for s in snap.services)


def test_interactive_worker_health_exposes_last_known_status():
    worker = "worker-rig-01"
    snap1 = get_worker_health_snapshot(worker, timeout_budget_ms=2000, interactive=True)
    snap2 = get_worker_health_snapshot(worker, timeout_budget_ms=2000, interactive=True)
    assert snap2.last_known_status is not None
    assert snap2.last_known_status.get("checked_at")
    assert get_last_known_worker_status(worker) is not None
