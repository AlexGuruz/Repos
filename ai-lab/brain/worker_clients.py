"""
Worker service HTTP clients (Guru §26). Normalized wrappers for Worker Assistant, n8n, Ollama.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

from brain import telemetry
from brain.worker_services import (
    get_worker_assistant_url,
    get_worker_n8n_url,
    get_worker_ollama_base_url,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_get(url: str, path: str, timeout_sec: float = 5.0) -> dict[str, Any]:
    """GET and return normalized { status, data, error, ... }."""
    full = (url.rstrip("/") + "/" + path.lstrip("/")).replace("/?", "?")
    try:
        req = urllib.request.Request(full, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
        return {"status": "ok", "data": data, "error": None, "timestamp": _now_iso()}
    except urllib.error.HTTPError as e:
        return {"status": "error", "data": None, "error": f"HTTP {e.code}", "timestamp": _now_iso()}
    except Exception as e:
        return {"status": "error", "data": None, "error": str(e), "timestamp": _now_iso()}


def _http_post(url: str, path: str, payload: dict[str, Any], timeout_sec: float = 10.0) -> dict[str, Any]:
    """POST JSON and return normalized { status, data, error, ... }."""
    full = (url.rstrip("/") + "/" + path.lstrip("/")).replace("/?", "?")
    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(full, data=body, method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw.strip() else {}
        return {"status": "ok", "data": data, "error": None, "timestamp": _now_iso()}
    except urllib.error.HTTPError as e:
        return {"status": "error", "data": None, "error": f"HTTP {e.code}", "timestamp": _now_iso()}
    except Exception as e:
        return {"status": "error", "data": None, "error": str(e), "timestamp": _now_iso()}


def worker_assistant_health(worker_name: str = "worker-rig-01") -> dict[str, Any]:
    """GET /health; normalized return with service, worker."""
    url = get_worker_assistant_url(worker_name)
    if not url:
        out = {"status": "error", "service": "worker_assistant", "worker": worker_name, "data": None, "error": "WORKER_ASSISTANT_URL not set", "timestamp": _now_iso()}
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail="env not set")
        return out
    out = _http_get(url, "/health", timeout_sec=3.0)
    out["service"] = "worker_assistant"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="worker_assistant", status="ok")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail=out.get("error"))
    return out


def worker_assistant_index_repo(
    repo_path: str,
    worker_name: str = "worker-rig-01",
    **kwargs: Any,
) -> dict[str, Any]:
    """POST /index_repo (if endpoint exists); normalized return."""
    url = get_worker_assistant_url(worker_name)
    if not url:
        out = {"status": "error", "service": "worker_assistant", "worker": worker_name, "data": None, "error": "WORKER_ASSISTANT_URL not set", "timestamp": _now_iso()}
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail="env not set")
        return out
    payload = {"repo_path": repo_path, **kwargs}
    out = _http_post(url, "/index_repo", payload, timeout_sec=30.0)
    out["service"] = "worker_assistant"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="worker_assistant", action="index_repo")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail=out.get("error"))
    return out


def worker_assistant_retrieve(
    query: str,
    worker_name: str = "worker-rig-01",
    **kwargs: Any,
) -> dict[str, Any]:
    """POST /retrieve (if endpoint exists); normalized return."""
    url = get_worker_assistant_url(worker_name)
    if not url:
        out = {"status": "error", "service": "worker_assistant", "worker": worker_name, "data": None, "error": "WORKER_ASSISTANT_URL not set", "timestamp": _now_iso()}
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail="env not set")
        return out
    payload = {"query": query, **kwargs}
    out = _http_post(url, "/retrieve", payload, timeout_sec=10.0)
    out["service"] = "worker_assistant"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="worker_assistant", action="retrieve")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail=out.get("error"))
    return out


def worker_assistant_promote_repo_index(
    repo_id: str,
    staging_version: str,
    worker_name: str = "worker-rig-01",
) -> dict[str, Any]:
    """POST /promote_repo_index (if endpoint exists); normalized return."""
    url = get_worker_assistant_url(worker_name)
    if not url:
        out = {
            "status": "error",
            "service": "worker_assistant",
            "worker": worker_name,
            "data": None,
            "error": "WORKER_ASSISTANT_URL not set",
            "timestamp": _now_iso(),
        }
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail=out.get("error"))
        return out
    payload = {"repo_id": repo_id, "staging_version": staging_version}
    out = _http_post(url, "/promote_repo_index", payload, timeout_sec=30.0)
    out["service"] = "worker_assistant"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="worker_assistant", action="promote_repo_index")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="worker_assistant", detail=out.get("error"))
    return out


def worker_n8n_trigger(
    workflow_id: str,
    payload: dict[str, Any],
    worker_name: str = "worker-rig-01",
) -> dict[str, Any]:
    """Trigger n8n workflow; approval should be checked by caller. Normalized return."""
    url = get_worker_n8n_url(worker_name)
    if not url:
        out = {"status": "error", "service": "n8n", "worker": worker_name, "data": None, "error": "WORKER_N8N_URL not set", "timestamp": _now_iso()}
        telemetry.log_event("worker_service_failure", worker=worker_name, service="n8n", detail="env not set")
        return out
    # n8n webhook pattern: often POST /webhook/<id> or /webhook-test/<id>
    path = f"/webhook/{workflow_id}" if workflow_id else "/webhook"
    out = _http_post(url, path, payload, timeout_sec=15.0)
    out["service"] = "n8n"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="n8n", action="trigger")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="n8n", detail=out.get("error"))
    return out


def worker_ollama_tags(worker_name: str = "worker-rig-01") -> dict[str, Any]:
    """GET /api/tags; normalized return."""
    url = get_worker_ollama_base_url(worker_name)
    if not url:
        out = {"status": "error", "service": "ollama", "worker": worker_name, "data": None, "error": "OLLAMA_HOST not set", "timestamp": _now_iso()}
        telemetry.log_event("worker_service_failure", worker=worker_name, service="ollama", detail="env not set")
        return out
    out = _http_get(url, "/api/tags", timeout_sec=5.0)
    out["service"] = "ollama"
    out["worker"] = worker_name
    if out.get("status") == "ok":
        telemetry.log_event("worker_service_call", worker=worker_name, service="ollama", action="tags")
    else:
        telemetry.log_event("worker_service_failure", worker=worker_name, service="ollama", detail=out.get("error"))
    return out
