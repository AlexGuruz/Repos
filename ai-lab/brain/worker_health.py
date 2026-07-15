"""
Worker service health checks (Guru §26). Worker Assistant, n8n, Ollama — normalized status, no unhandled exceptions.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime, timezone
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any

from brain.worker_tunnel import get_tunnel_status
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
    checked_at: str
    timeout_budget_ms: int | None = None
    worker_status: str | None = None
    last_known_status: dict[str, Any] | None = None
    tunnel_status: dict[str, Any] | None = None


_LAST_STATUS_BY_WORKER: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _service_timeout(name: str, timeout_sec: float) -> ServiceHealth:
    return ServiceHealth(
        name=name,
        ok=False,
        url=None,
        status_code=None,
        detail=f"timeout after {int(timeout_sec * 1000)}ms budget",
        latency_ms=None,
    )


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


def check_worker_assistant(worker_name: str = "worker-rig-01", timeout_sec: float = 3.0) -> ServiceHealth:
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
    code, lat, detail = _http_get(url, "/health", timeout_sec=timeout_sec)
    return ServiceHealth(
        name="worker_assistant",
        ok=code == 200,
        url=url.rstrip("/") + "/health",
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def check_worker_n8n(worker_name: str = "worker-rig-01", timeout_sec: float = 3.0) -> ServiceHealth:
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
    code, lat, detail = _http_get(url, "/", timeout_sec=timeout_sec)
    return ServiceHealth(
        name="n8n",
        ok=code in (200, 302, 307),
        url=url.rstrip("/") + "/",
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def check_worker_ollama(worker_name: str = "worker-rig-01", timeout_sec: float = 4.0) -> ServiceHealth:
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
    code, lat, detail = _http_get(url, "/api/tags", timeout_sec=timeout_sec)
    return ServiceHealth(
        name="ollama",
        ok=code == 200,
        url=(url.rstrip("/") + "/api/tags") if url else None,
        status_code=code,
        detail=detail,
        latency_ms=lat,
    )


def get_last_known_worker_status(worker_name: str = "worker-rig-01") -> dict[str, Any] | None:
    cached = _LAST_STATUS_BY_WORKER.get(worker_name)
    return dict(cached) if isinstance(cached, dict) else None


def get_worker_health_snapshot(
    worker_name: str = "worker-rig-01",
    *,
    timeout_budget_ms: int | None = None,
    interactive: bool = False,
) -> WorkerHealthSnapshot:
    """Run worker health checks. Interactive mode applies a strict wall-clock timeout budget."""
    import os

    ssh_configured = bool((os.environ.get("WORKER_SSH_HOST") or "").strip())
    checked_at = _now_iso()
    budget_ms = int(timeout_budget_ms or 0) if interactive else None
    total_start = time.perf_counter()
    service_budget_ms = budget_ms
    if interactive and budget_ms:
        # Allow enough wall time for remote WA (;8765) — previously capped at 1.2s and
        # falsely reported WA down during investor-demo preflight while curl /health was 200.
        service_budget_ms = max(300, min(4000, int(budget_ms * 0.8)))
    per_service_timeout = 3.0
    if interactive and service_budget_ms:
        per_service_timeout = max(0.15, min(3.0, service_budget_ms / 1000.0))

    services_map: dict[str, ServiceHealth] = {
        "worker_assistant": _service_timeout("worker_assistant", per_service_timeout) if interactive else check_worker_assistant(worker_name, timeout_sec=per_service_timeout),
        "n8n": _service_timeout("n8n", per_service_timeout) if interactive else check_worker_n8n(worker_name, timeout_sec=per_service_timeout),
        "ollama": _service_timeout("ollama", per_service_timeout) if interactive else check_worker_ollama(worker_name, timeout_sec=per_service_timeout),
    }
    if interactive and budget_ms:
        start = time.perf_counter()
        pool = ThreadPoolExecutor(max_workers=3)
        futures = {
            pool.submit(check_worker_assistant, worker_name, per_service_timeout): "worker_assistant",
            pool.submit(check_worker_n8n, worker_name, per_service_timeout): "n8n",
            pool.submit(check_worker_ollama, worker_name, per_service_timeout): "ollama",
        }
        try:
            try:
                for fut in as_completed(futures, timeout=max(0.05, service_budget_ms / 1000.0)):
                    name = futures[fut]
                    try:
                        services_map[name] = fut.result()
                    except Exception as e:
                        services_map[name] = ServiceHealth(
                            name=name,
                            ok=False,
                            url=None,
                            status_code=None,
                            detail=str(e),
                            latency_ms=None,
                        )
                    if (time.perf_counter() - start) * 1000.0 >= service_budget_ms:
                        break
            except TimeoutError:
                pass
            for fut, name in futures.items():
                if not fut.done():
                    services_map[name] = _service_timeout(name, per_service_timeout)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
    services = [services_map["worker_assistant"], services_map["n8n"], services_map["ollama"]]

    tunnel_status = None
    if interactive and budget_ms:
        elapsed_ms = (time.perf_counter() - total_start) * 1000.0
        remaining_ms = max(50.0, float(budget_ms) - elapsed_ms)
        tunnel_budget_sec = max(0.05, min(0.35, remaining_ms / 1000.0))
        tunnel_status = get_tunnel_status(
            worker_name,
            per_port_timeout_sec=max(0.05, min(0.2, tunnel_budget_sec)),
            total_timeout_sec=tunnel_budget_sec,
        )
    else:
        tunnel_status = get_tunnel_status(worker_name)

    all_ok = all(s.ok for s in services)
    worker_status = "online" if all_ok and bool(tunnel_status and tunnel_status.get("likely_up")) else "offline_or_unreachable"
    last_known = get_last_known_worker_status(worker_name)
    snap = WorkerHealthSnapshot(
        worker_name=worker_name,
        ssh_configured=ssh_configured,
        services=services,
        all_ok=all_ok,
        checked_at=checked_at,
        timeout_budget_ms=budget_ms,
        worker_status=worker_status,
        last_known_status=last_known,
        tunnel_status=tunnel_status,
    )
    _LAST_STATUS_BY_WORKER[worker_name] = {
        "checked_at": checked_at,
        "worker_status": worker_status,
        "all_ok": all_ok,
        "services": [asdict(s) for s in services],
        "tunnel_status": tunnel_status,
    }
    return snap


def worker_health_snapshot_to_dict(snap: WorkerHealthSnapshot) -> dict[str, Any]:
    """For API/telemetry: snapshot as dict."""
    return {
        "worker_name": snap.worker_name,
        "ssh_configured": snap.ssh_configured,
        "all_ok": snap.all_ok,
        "services": [asdict(s) for s in snap.services],
        "checked_at": snap.checked_at,
        "timeout_budget_ms": snap.timeout_budget_ms,
        "worker_status": snap.worker_status,
        "last_known_status": snap.last_known_status,
        "tunnel_status": snap.tunnel_status,
    }
