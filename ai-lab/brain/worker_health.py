"""
Worker service health checks (Guru §26). Worker Assistant, n8n, Ollama — normalized status, no unhandled exceptions.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

from brain.worker_services import (
    get_worker_assistant_url,
    get_worker_n8n_url,
    get_worker_ollama_base_url,
)


@dataclass
class ServiceHealth:
    name: str
    ok: bool
    url: str | None
    status_code: int | None
    detail: str
    latency_ms: float | None


@dataclass
class WorkerHealthSnapshot:
    worker_name: str
    ssh_configured: bool
    services: list[ServiceHealth]
    all_ok: bool


def _http_get(url: str, path: str, timeout_sec: float = 3.0) -> tuple[int | None, float | None, str]:
    """GET url+path; return (status_code, latency_ms, detail). Never raises."""
    full = (url.rstrip("/") + "/" + path.lstrip("/")).replace("/?", "?")
    start = time.perf_counter()
    try:
        req = urllib.request.Request(full, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = resp.getcode()
            _ = resp.read()
        return code, (time.perf_counter() - start) * 1000, "ok"
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - start) * 1000, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, None, str(e.reason) if getattr(e, "reason", None) else str(e)
    except TimeoutError:
        return None, None, "timeout"
    except Exception as e:
        return None, None, str(e)


def check_worker_assistant(worker_name: str = "worker-rig-01") -> ServiceHealth:
    """GET /health on Worker Assistant."""
    url = get_worker_assistant_url(worker_name)
    if not url:
        return ServiceHealth(
            name="worker_assistant",
            ok=False,
            url=None,
            status_code=None,
            detail="WORKER_ASSISTANT_URL not set",
            latency_ms=None,
        )
    code, lat, detail = _http_get(url, "/health", timeout_sec=3.0)
    return ServiceHealth(
        name="worker_assistant",
        ok=code == 200,
        url=url.rstrip("/") + "/health",
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def check_worker_n8n(worker_name: str = "worker-rig-01") -> ServiceHealth:
    """GET / on n8n."""
    url = get_worker_n8n_url(worker_name)
    if not url:
        return ServiceHealth(
            name="n8n",
            ok=False,
            url=None,
            status_code=None,
            detail="WORKER_N8N_URL not set",
            latency_ms=None,
        )
    code, lat, detail = _http_get(url, "/", timeout_sec=3.0)
    return ServiceHealth(
        name="n8n",
        ok=code in (200, 302, 307),
        url=url.rstrip("/") + "/",
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def check_worker_ollama(worker_name: str = "worker-rig-01") -> ServiceHealth:
    """GET /api/tags on Ollama."""
    url = get_worker_ollama_base_url(worker_name)
    if not url:
        return ServiceHealth(
            name="ollama",
            ok=False,
            url=None,
            status_code=None,
            detail="OLLAMA_HOST not set",
            latency_ms=None,
        )
    code, lat, detail = _http_get(url, "/api/tags", timeout_sec=4.0)
    return ServiceHealth(
        name="ollama",
        ok=code == 200,
        url=(url.rstrip("/") + "/api/tags") if url else None,
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def get_worker_health_snapshot(worker_name: str = "worker-rig-01") -> WorkerHealthSnapshot:
    """Run all service health checks; ssh_configured from WORKER_SSH_HOST."""
    import os
    ssh_configured = bool((os.environ.get("WORKER_SSH_HOST") or "").strip())
    services = [
        check_worker_assistant(worker_name),
        check_worker_n8n(worker_name),
        check_worker_ollama(worker_name),
    ]
    all_ok = all(s.ok for s in services)
    return WorkerHealthSnapshot(
        worker_name=worker_name,
        ssh_configured=ssh_configured,
        services=services,
        all_ok=all_ok,
    )


def worker_health_snapshot_to_dict(snap: WorkerHealthSnapshot) -> dict[str, Any]:
    """For API/telemetry: snapshot as dict."""
    return {
        "worker_name": snap.worker_name,
        "ssh_configured": snap.ssh_configured,
        "all_ok": snap.all_ok,
        "services": [asdict(s) for s in snap.services],
    }
