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


def _registry_base_url(svc: dict[str, Any], *, normalize: bool = False) -> str | None:
    base = (svc.get("base_url") or "").strip()
    if not base:
        return None
    if normalize:
        base = _normalize_ollama_host(base)
    return base.rstrip("/") or None


def _resolve_service_url(
    svc: dict[str, Any] | None,
    legacy_env_var: str,
    *,
    normalize: bool = False,
) -> str | None:
    """
    Resolve a service URL without letting one worker's legacy env override another worker.

    Services with a dedicated per-worker env_var should only use that env var or their
    registry base_url. The legacy env fallback is reserved for older registry entries
    that do not define per-worker env vars.
    """
    if isinstance(svc, dict):
        env_var = (svc.get("env_var") or "").strip()
        if env_var:
            url = (os.environ.get(env_var) or "").strip()
            if url:
                if normalize:
                    url = _normalize_ollama_host(url)
                return url.rstrip("/") or None
            return _registry_base_url(svc, normalize=normalize)

    url = (os.environ.get(legacy_env_var) or "").strip()
    if url:
        if normalize:
            url = _normalize_ollama_host(url)
        return url.rstrip("/") or None
    if isinstance(svc, dict):
        return _registry_base_url(svc, normalize=normalize)
    return None


def get_worker_assistant_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Worker Assistant base URL from worker-specific env/registry settings."""
    svc = get_worker_service(worker_name, "worker_assistant")
    return _resolve_service_url(svc, "WORKER_ASSISTANT_URL")


def get_worker_n8n_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve n8n base URL from worker-specific env/registry settings."""
    svc = get_worker_service(worker_name, "n8n")
    return _resolve_service_url(svc, "WORKER_N8N_URL")


def get_worker_ollama_base_url(worker_name: str = "worker-rig-01") -> str | None:
    """Resolve Ollama base URL from worker-specific env/registry settings."""
    svc = get_worker_service(worker_name, "ollama")
    return _resolve_service_url(svc, "OLLAMA_HOST", normalize=True)


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
