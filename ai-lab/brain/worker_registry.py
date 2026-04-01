"""
Worker registry loader (Guru §26). Load worker and service definitions from ops/registry/workers.yaml.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from brain.ops_registry import get_ops_root
from brain.ops_registry import _load_yaml as _load_yaml_ops


def _worker_registry_path(ops_root: Path | None = None) -> Path:
    root = ops_root or get_ops_root()
    return root / "registry" / "workers.yaml"


def load_worker_registry(ops_root: Path | None = None) -> dict[str, Any]:
    """Load workers.yaml. Returns { workers: { name: {...} } }. Never raises; returns {} on missing/fail."""
    try:
        data = _load_yaml_ops(_worker_registry_path(ops_root))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_worker(worker_name: str, ops_root: Path | None = None) -> dict[str, Any] | None:
    """Return worker dict by name, or None if missing."""
    data = load_worker_registry(ops_root)
    workers = data.get("workers")
    if not isinstance(workers, dict):
        return None
    return workers.get(worker_name)


def get_worker_service(
    worker_name: str,
    service_name: str,
    ops_root: Path | None = None,
) -> dict[str, Any] | None:
    """Return service definition for a worker (from service_definitions or legacy)."""
    w = get_worker(worker_name, ops_root)
    if not w:
        return None
    defs = w.get("service_definitions") or {}
    if isinstance(defs, dict) and service_name in defs:
        return defs.get(service_name)
    # Legacy: services list only
    services = w.get("services") or []
    if service_name in services:
        return {"service": service_name}
    return None


def list_worker_services(worker_name: str, ops_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return all service definitions for a worker as { service_name: {...} }."""
    w = get_worker(worker_name, ops_root)
    if not w:
        return {}
    defs = w.get("service_definitions")
    if isinstance(defs, dict):
        return dict(defs)
    out: dict[str, dict[str, Any]] = {}
    for s in w.get("services") or []:
        if isinstance(s, str):
            out[s] = {"service": s}
    return out
