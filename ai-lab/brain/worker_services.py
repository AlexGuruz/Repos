"""
Worker service URL resolver (Guru §26). Resolve effective service URLs from env + registry.
"""
from __future__ import annotations

import os
from typing import Any

from brain.worker_registry import get_worker_service


def _normalize_ollama_host(value: str) -> str:
    """Ensure OLLAMA_HOST has scheme for HTTP calls if missing."""
    v = (value or "").strip()
    if v and not v.startswith("http://") and not v.startswith("https://"):
        return f"http://{v}"
    return v


def get_worker_assistant_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Worker Assistant base URL: service env_var, registry base_url, else legacy env."""
    svc = get_worker_service(worker_name, "worker_assistant")
    if isinstance(svc, dict):
        env_var = (svc.get("env_var") or "").strip()
        if env_var:
            url = (os.environ.get(env_var) or "").strip()
            if url:
                return url.rstrip("/") or None
        base = (svc.get("base_url") or "").strip()
        if base:
            return base.rstrip("/") or None
    url = (os.environ.get("WORKER_ASSISTANT_URL") or "").strip()
    if url:
        return url.rstrip("/") or None
    return None


def get_worker_n8n_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve n8n base URL: service env_var, registry base_url, else legacy env."""
    svc = get_worker_service(worker_name, "n8n")
    if isinstance(svc, dict):
        env_var = (svc.get("env_var") or "").strip()
        if env_var:
            url = (os.environ.get(env_var) or "").strip()
            if url:
                return url.rstrip("/") or None
        base = (svc.get("base_url") or "").strip()
        if base:
            return base.rstrip("/") or None
    url = (os.environ.get("WORKER_N8N_URL") or "").strip()
    if url:
        return url.rstrip("/") or None
    return None


def get_worker_ollama_base_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Ollama base URL: service env_var, registry base_url, else legacy env."""
    svc = get_worker_service(worker_name, "ollama")
    if isinstance(svc, dict):
        env_var = (svc.get("env_var") or "").strip()
        if env_var:
            url = (os.environ.get(env_var) or "").strip()
            if url:
                return _normalize_ollama_host(url).rstrip("/") or None
        base = (svc.get("base_url") or "").strip()
        if base:
            return _normalize_ollama_host(base).rstrip("/") or None
    url = (os.environ.get("OLLAMA_HOST") or "").strip()
    if url:
        return _normalize_ollama_host(url).rstrip("/") or None
    return None


def get_service_url(service_name: str, worker_name: str = "worker-rig-01") -> str | None:
    """Generic resolver: worker_assistant -> get_worker_assistant_url, n8n -> get_worker_n8n_url, ollama -> get_worker_ollama_base_url."""
    if service_name == "worker_assistant":
        return get_worker_assistant_url(worker_name)
    if service_name == "n8n":
        return get_worker_n8n_url(worker_name)
    if service_name == "ollama":
        return get_worker_ollama_base_url(worker_name)
    svc = get_worker_service(worker_name, service_name)
    if isinstance(svc, dict) and svc.get("base_url"):
        return (svc.get("base_url") or "").strip().rstrip("/") or None
    return None
