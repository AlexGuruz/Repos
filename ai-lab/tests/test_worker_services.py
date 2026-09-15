"""
Tests for brain.worker_services (Guru §26). URL resolution from env and registry.
"""
from __future__ import annotations

import os
import pytest

from brain.worker_services import (
    get_worker_assistant_url,
    get_worker_n8n_url,
    get_worker_ollama_base_url,
    get_service_url,
)


def test_get_worker_assistant_url_from_registry_when_env_unset():
    # With env unset, should fall back to the selected worker's registry base_url.
    env_val = os.environ.pop("WORKER_ASSISTANT_URL_SECONDARY", None)
    legacy_val = os.environ.pop("WORKER_ASSISTANT_URL", None)
    try:
        assert get_worker_assistant_url("worker-rig-01") == "http://127.0.0.1:8766"
    finally:
        if env_val is not None:
            os.environ["WORKER_ASSISTANT_URL_SECONDARY"] = env_val
        if legacy_val is not None:
            os.environ["WORKER_ASSISTANT_URL"] = legacy_val


def test_get_worker_assistant_url_per_worker_env_override(monkeypatch):
    monkeypatch.setenv("WORKER_ASSISTANT_URL_SECONDARY", "http://127.0.0.1:18766")
    assert get_worker_assistant_url("worker-rig-01") == "http://127.0.0.1:18766"


def test_secondary_worker_ignores_primary_legacy_env(monkeypatch):
    monkeypatch.setenv("WORKER_ASSISTANT_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("WORKER_N8N_URL", "http://127.0.0.1:5678")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:11434")
    monkeypatch.delenv("WORKER_ASSISTANT_URL_SECONDARY", raising=False)
    monkeypatch.delenv("WORKER_N8N_URL_SECONDARY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST_SECONDARY", raising=False)

    assert get_worker_assistant_url("worker-rig-01") == "http://127.0.0.1:8766"
    assert get_worker_n8n_url("worker-rig-01") == "http://127.0.0.1:5679"
    assert get_worker_ollama_base_url("worker-rig-01") == "http://127.0.0.1:11435"


def test_primary_worker_uses_primary_legacy_env(monkeypatch):
    monkeypatch.setenv("WORKER_ASSISTANT_URL", "http://127.0.0.1:18765")
    monkeypatch.setenv("WORKER_N8N_URL", "http://127.0.0.1:15678")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:111434")

    assert get_worker_assistant_url("worker-rig-02") == "http://127.0.0.1:18765"
    assert get_worker_n8n_url("worker-rig-02") == "http://127.0.0.1:15678"
    assert get_worker_ollama_base_url("worker-rig-02") == "http://127.0.0.1:111434"


def test_get_service_url_generic():
    url = get_service_url("worker_assistant", "worker-rig-01")
    assert url is None or (isinstance(url, str) and "http" in url)
    url2 = get_service_url("n8n", "worker-rig-01")
    assert url2 is None or (isinstance(url2, str) and "http" in url2)
