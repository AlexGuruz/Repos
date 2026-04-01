"""
Worker tunnel status (Guru §26). Check local tunnel port reachability; no full tunnel manager yet.
"""
from __future__ import annotations

import socket
from typing import Any

from brain.worker_registry import get_worker


def is_local_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Return True if host:port accepts a connection (e.g. tunnel listening)."""
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except (OSError, socket.error):
        return False


def get_tunnel_status(worker_name: str = "worker-rig-01") -> dict[str, Any]:
    """Return expected_ports, reachable_ports, missing_ports, likely_up, detail."""
    w = get_worker(worker_name)
    expected = [8765, 5678, 11434]
    if w and w.get("service_definitions"):
        expected = []
        for svc in w.get("service_definitions", {}).values():
            if isinstance(svc, dict) and isinstance(svc.get("local_tunnel_port"), int):
                expected.append(svc["local_tunnel_port"])
        if not expected:
            expected = [8765, 5678, 11434]
    reachable = [p for p in expected if is_local_port_open(p)]
    missing = [p for p in expected if p not in reachable]
    likely_up = len(missing) == 0
    detail = "Tunnel appears up." if likely_up else f"Missing tunnel ports: {missing}. Start tunnel or check worker."
    return {
        "worker_name": worker_name,
        "expected_ports": expected,
        "reachable_ports": reachable,
        "missing_ports": missing,
        "likely_up": likely_up,
        "detail": detail,
    }
