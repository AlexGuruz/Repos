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


def _service_env_url(svc: Any, *, normalize=None) -> str | None:
    if not isinstance(svc, dict):
        return None
    env_var = (svc.get("env_var") or "").strip()
    if not env_var:
        return None
    url = (os.environ.get(env_var) or "").strip()
    if normalize is not None:
        url = normalize(url)
    return url.rstrip("/") or None


def _registry_base_url(svc: Any, *, normalize=None) -> str | None:
    if not isinstance(svc, dict):
        return None
    url = (svc.get("base_url") or "").strip()
    if normalize is not None:
        url = normalize(url)
    return url.rstrip("/") or None


def _legacy_env_allowed(svc: Any, legacy_env_var: str) -> bool:
    if not isinstance(svc, dict):
        return True
    env_var = (svc.get("env_var") or "").strip()
    return not env_var or env_var == legacy_env_var


def get_worker_assistant_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Worker Assistant URL without leaking primary legacy envs to scoped workers."""
    svc = get_worker_service(worker_name, "worker_assistant")
    url = _service_env_url(svc)
    if url:
        return url
    if _legacy_env_allowed(svc, "WORKER_ASSISTANT_URL"):
        url = (os.environ.get("WORKER_ASSISTANT_URL") or "").strip()
        if url:
            return url.rstrip("/") or None
    return _registry_base_url(svc)


def get_worker_n8n_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve n8n URL without leaking primary legacy envs to scoped workers."""
    svc = get_worker_service(worker_name, "n8n")
    url = _service_env_url(svc)
    if url:
        return url
    if _legacy_env_allowed(svc, "WORKER_N8N_URL"):
        url = (os.environ.get("WORKER_N8N_URL") or "").strip()
        if url:
            return url.rstrip("/") or None
    return _registry_base_url(svc)


def get_worker_ollama_base_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Ollama URL without leaking primary legacy envs to scoped workers."""
    svc = get_worker_service(worker_name, "ollama")
    url = _service_env_url(svc, normalize=_normalize_ollama_host)
    if url:
        return url
    if _legacy_env_allowed(svc, "OLLAMA_HOST"):
        url = (os.environ.get("OLLAMA_HOST") or "").strip()
        if url:
            return _normalize_ollama_host(url).rstrip("/") or None
    return _registry_base_url(svc, normalize=_normalize_ollama_host)


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
