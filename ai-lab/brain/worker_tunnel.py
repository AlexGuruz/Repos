"""
Worker tunnel status (Guru §26). Check local tunnel port reachability; no full tunnel manager yet.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import socket
import time
from typing import Any

from brain.worker_registry import get_worker


def is_local_port_open(port: int, host: str = "127.0.0.1", timeout_sec: float = 2.0) -> bool:
    """Return True if host:port accepts a connection (e.g. tunnel listening)."""
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except (OSError, socket.error):
        return False


def get_tunnel_status(
    worker_name: str = "worker-rig-01",
    *,
    per_port_timeout_sec: float = 2.0,
    total_timeout_sec: float | None = None,
) -> dict[str, Any]:
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
    reachable: list[int] = []
    missing: list[int] = []
    started = time.perf_counter()
    budget = total_timeout_sec if total_timeout_sec is not None else max(0.5, per_port_timeout_sec * len(expected))
    pool = ThreadPoolExecutor(max_workers=max(1, len(expected)))
    try:
        fut_to_port = {
            pool.submit(is_local_port_open, p, "127.0.0.1", per_port_timeout_sec): p for p in expected
        }
        deadline = started + max(0.05, budget)
        try:
            for fut in as_completed(fut_to_port, timeout=max(0.05, budget)):
                p = fut_to_port[fut]
                try:
                    if fut.result():
                        reachable.append(p)
                    else:
                        missing.append(p)
                except Exception:
                    missing.append(p)
                if time.perf_counter() >= deadline:
                    break
        except TimeoutError:
            pass
        for fut, p in fut_to_port.items():
            if not fut.done() and p not in missing and p not in reachable:
                missing.append(p)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
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
