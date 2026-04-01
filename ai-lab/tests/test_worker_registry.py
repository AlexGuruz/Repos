"""
Tests for brain.worker_registry (Guru §26).
"""
from __future__ import annotations

import pytest

from brain.worker_registry import load_worker_registry, get_worker, get_worker_service, list_worker_services


def test_load_worker_registry_returns_dict():
    data = load_worker_registry()
    assert isinstance(data, dict)


def test_get_worker_main_brain():
    w = get_worker("main-brain")
    assert w is not None
    assert w.get("host") == "local"
    assert "purpose" in w or "capabilities" in w


def test_get_worker_rig_01_has_service_definitions():
    w = get_worker("worker-rig-01")
    assert w is not None
    defs = w.get("service_definitions")
    assert isinstance(defs, dict)
    assert "worker_assistant" in defs
    assert "n8n" in defs
    assert "ollama" in defs


def test_get_worker_service_worker_assistant():
    svc = get_worker_service("worker-rig-01", "worker_assistant")
    assert svc is not None
    assert svc.get("remote_port") == 8765
    assert svc.get("env_var") == "WORKER_ASSISTANT_URL"
    assert svc.get("health_path") == "/health"


def test_list_worker_services():
    services = list_worker_services("worker-rig-01")
    assert "worker_assistant" in services
    assert "n8n" in services
    assert "ollama" in services


def test_get_worker_missing_returns_none():
    assert get_worker("nonexistent-worker") is None


def test_get_worker_service_missing_returns_none():
    assert get_worker_service("worker-rig-01", "nonexistent") is None
