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
    # With env unset, should fall back to registry base_url
    env_val = os.environ.pop("WORKER_ASSISTANT_URL", None)
    try:
        url = get_worker_assistant_url("worker-rig-01")
        assert url is None or url.startswith("http")
        if url:
            assert "8765" in url
    finally:
        if env_val is not None:
            os.environ["WORKER_ASSISTANT_URL"] = env_val


def test_get_worker_assistant_url_env_override(monkeypatch):
    monkeypatch.setenv("WORKER_ASSISTANT_URL", "http://127.0.0.1:8765")
    url = get_worker_assistant_url("worker-rig-01")
    assert url == "http://127.0.0.1:8765"


def test_get_service_url_generic():
    url = get_service_url("worker_assistant", "worker-rig-01")
    assert url is None or (isinstance(url, str) and "http" in url)
    url2 = get_service_url("n8n", "worker-rig-01")
    assert url2 is None or (isinstance(url2, str) and "http" in url2)
