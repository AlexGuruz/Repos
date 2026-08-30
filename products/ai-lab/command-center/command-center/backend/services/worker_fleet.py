"""
Canonical Acheron fleet map (docs_source/WORKER_CURRENT.md).

power-1 = worker_assistant :8765 + n8n :5678 (no Ollama).
worker-node = WA :8766 + n8n :5679 + GPU Ollama :11435.
acheron = local Ollama :11434 (not a tunneled worker).
"""
from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_CACHE_TTL_S = 2.0

# WORKER_CURRENT.md — do not invent extra services (Kylo/Kafka/n8n-on-host).
FLEET_NODES: list[dict[str, Any]] = [
    {
        "id": "acheron",
        "display_name": "Acheron (main rig)",
        "role": "main_rig",
        "aliases": ["main", "main-brain"],
        "notes": "Local Ollama only. Do not treat :11434 as a worker tunnel.",
        "tunnel_ports": [],
        "services": [
            {
                "name": "ollama_local",
                "url": "http://127.0.0.1:11434",
                "path": "/api/tags",
                "port": 11434,
                "ok_codes": (200,),
                "critical": False,
            },
        ],
    },
    {
        "id": "power-1",
        "display_name": "power-1 (primary worker)",
        "role": "primary_worker",
        "aliases": ["worker-rig-02", "CameraServer", "CAMERASERVER"],
        "notes": "GrowFlow writers, Kylo, n8n, worker_assistant. No Ollama on this box.",
        "tunnel_ports": [8765, 5678],
        "services": [
            {
                "name": "worker_assistant",
                "url": "http://127.0.0.1:8765",
                "path": "/health",
                "port": 8765,
                "ok_codes": (200,),
                "critical": True,
            },
            {
                "name": "n8n",
                "url": "http://127.0.0.1:5678",
                "path": "/",
                "port": 5678,
                "ok_codes": (200, 302, 307),
                "critical": False,
            },
        ],
    },
    {
        "id": "worker-node",
        "display_name": "worker-node (GPU worker)",
        "role": "gpu_worker",
        "aliases": ["worker-rig-01"],
        "notes": "GPU Ollama via Acheron tunnel :11435. Secondary WA/n8n tunnels.",
        "tunnel_ports": [8766, 5679, 11435],
        "services": [
            {
                "name": "worker_assistant",
                "url": "http://127.0.0.1:8766",
                "path": "/health",
                "port": 8766,
                "ok_codes": (200,),
                "critical": True,
            },
            {
                "name": "n8n",
                "url": "http://127.0.0.1:5679",
                "path": "/",
                "port": 5679,
                "ok_codes": (200, 302, 307),
                "critical": False,
            },
            {
                "name": "ollama_gpu",
                "url": "http://127.0.0.1:11435",
                "path": "/api/tags",
                "port": 11435,
                "ok_codes": (200,),
                "critical": False,
            },
        ],
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_node_id(name: str) -> str | None:
    key = (name or "").strip()
    if not key:
        return None
    for node in FLEET_NODES:
        if node["id"] == key or key in node.get("aliases", []):
            return node["id"]
    return None


def is_local_port_open(port: int, host: str = "127.0.0.1", timeout_sec: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False


def _http_get(url: str, path: str, timeout_sec: float = 0.6) -> tuple[int | None, float | None, str]:
    full = url.rstrip("/") + "/" + path.lstrip("/")
    start = time.perf_counter()
    try:
        req = urllib.request.Request(full, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            code = resp.getcode()
            _ = resp.read(2048)
        return code, (time.perf_counter() - start) * 1000, "ok"
    except urllib.error.HTTPError as e:
        return e.code, (time.perf_counter() - start) * 1000, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", None)
        return None, (time.perf_counter() - start) * 1000, str(reason) if reason else str(e)
    except Exception as e:
        msg = str(e) or type(e).__name__
        if "Empty" in msg or "empty" in msg.lower():
            return None, (time.perf_counter() - start) * 1000, "empty HTTP reply (port open, app not serving)"
        return None, (time.perf_counter() - start) * 1000, msg


def _probe_service(spec: dict[str, Any]) -> dict[str, Any]:
    port = spec.get("port")
    port_open = is_local_port_open(int(port)) if port else False
    code, lat, detail = _http_get(spec["url"], spec["path"])
    ok_codes = spec.get("ok_codes") or (200,)
    http_ok = code in ok_codes
    return {
        "name": spec["name"],
        "ok": http_ok,
        "http_ok": http_ok,
        "port_open": port_open,
        "url": spec["url"].rstrip("/") + spec["path"],
        "status_code": code,
        "detail": detail if not (port_open and not http_ok and not detail) else detail,
        "latency_ms": lat,
        "critical": bool(spec.get("critical")),
    }


def _probe_node(node: dict[str, Any]) -> dict[str, Any]:
    specs = node["services"]
    if len(specs) == 1:
        services = [_probe_service(specs[0])]
    else:
        with ThreadPoolExecutor(max_workers=len(specs)) as pool:
            services = list(pool.map(_probe_service, specs))
    expected = list(node.get("tunnel_ports") or [])
    reachable = [p for p in expected if is_local_port_open(p)]
    missing = [p for p in expected if p not in reachable]
    critical = [s for s in services if s.get("critical")]
    critical_ok = all(s["ok"] for s in critical) if critical else True
    wa = next((s for s in services if s["name"] == "worker_assistant"), None)
    worker_assistant_ok = bool(wa and wa["ok"])
    if critical and not critical_ok and any(s["port_open"] for s in critical):
        status = "degraded"
    elif critical_ok:
        status = "online"
    elif reachable and expected:
        status = "tunnel_up_http_down"
    else:
        status = "offline_or_unreachable"
    return {
        "id": node["id"],
        "display_name": node["display_name"],
        "role": node["role"],
        "aliases": node.get("aliases", []),
        "notes": node.get("notes", ""),
        "status": status,
        "critical_ok": critical_ok,
        "worker_assistant_ok": worker_assistant_ok,
        "all_ok": all(s["ok"] for s in services),
        "services": services,
        "tunnel_status": {
            "worker_name": node["id"],
            "expected_ports": expected,
            "reachable_ports": reachable,
            "missing_ports": missing,
            "likely_up": bool(expected) and not missing,
            "detail": (
                "Tunnel ports reachable."
                if expected and not missing
                else ("No tunneled ports (local services only)." if not expected else f"Missing tunnel ports: {missing}")
            ),
        },
    }


def build_fleet_map(*, use_cache: bool = True) -> dict[str, Any]:
    now = time.monotonic()
    if use_cache and _CACHE["payload"] is not None and (now - float(_CACHE["at"])) < _CACHE_TTL_S:
        return _CACHE["payload"]
    with ThreadPoolExecutor(max_workers=len(FLEET_NODES)) as pool:
        nodes = list(pool.map(_probe_node, FLEET_NODES))
    power = next((n for n in nodes if n["id"] == "power-1"), None)
    payload = {
        "ok": True,
        "source": "WORKER_CURRENT.md",
        "checked_at": _now(),
        "nodes": nodes,
        "primary_worker": "power-1",
        "critical_ok": bool(power and power["critical_ok"]),
        "summary": {n["id"]: n["status"] for n in nodes},
    }
    _CACHE["at"] = now
    _CACHE["payload"] = payload
    return payload


def health_for(name: str = "power-1") -> dict[str, Any]:
    nid = resolve_node_id(name) or "power-1"
    fleet = build_fleet_map()
    node = next((n for n in fleet["nodes"] if n["id"] == nid), None)
    if node is None:
        return {
            "worker_name": name,
            "ssh_configured": False,
            "all_ok": False,
            "worker_assistant_ok": False,
            "critical_ok": False,
            "worker_status": "unknown",
            "services": [],
            "tunnel_status": {"worker_name": name, "likely_up": False, "detail": "unknown node"},
            "last_checked": fleet["checked_at"],
            "error": f"unknown worker '{name}'",
            "fleet_summary": fleet["summary"],
        }
    return {
        "worker_name": node["id"],
        "display_name": node["display_name"],
        "role": node["role"],
        "notes": node["notes"],
        "ssh_configured": False,
        "all_ok": node["all_ok"],
        "worker_assistant_ok": node["worker_assistant_ok"],
        "critical_ok": node["critical_ok"],
        "worker_status": node["status"],
        "services": node["services"],
        "tunnel_status": node["tunnel_status"],
        "last_checked": fleet["checked_at"],
        "fleet_summary": fleet["summary"],
    }
