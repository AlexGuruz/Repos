#!/usr/bin/env python3
"""
Confirm the main rig can reach the worker node (Guru §26).
Run from ai-lab repo root with PYTHONPATH set so brain is importable.
Usage: python scripts/check_worker_connectivity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add ai-lab root so we can import brain
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main() -> int:
    worker_name = "worker-rig-01"
    try:
        from brain.worker_health import get_worker_health_snapshot, worker_health_snapshot_to_dict
        from brain.worker_tunnel import get_tunnel_status
    except ImportError as e:
        print("ERROR: Could not import brain. Run from ai-lab root with PYTHONPATH including that root.")
        print(f"  {e}")
        return 1

    tunnel = get_tunnel_status(worker_name)
    snap = get_worker_health_snapshot(worker_name)
    data = worker_health_snapshot_to_dict(snap)

    # One-line result
    tunnel_ok = tunnel.get("likely_up", False)
    all_ok = data.get("all_ok", False)
    if tunnel_ok and all_ok:
        print("Worker reachable: yes (tunnel up, all services ok)")
    elif all_ok:
        print("Worker reachable: partial (services ok; tunnel status: down or incomplete)")
    else:
        print("Worker reachable: no (tunnel or one or more services failed)")

    # Details
    print(f"  Tunnel: {'up' if tunnel_ok else 'down'} — {tunnel.get('detail', '')}")
    print(f"  Expected ports: {tunnel.get('expected_ports', [])}")
    print(f"  Reachable: {tunnel.get('reachable_ports', [])}")
    for s in data.get("services") or []:
        name = s.get("name", "?")
        ok = s.get("ok", False)
        lat = s.get("latency_ms")
        detail = s.get("detail", "")
        lat_str = f" {lat:.0f}ms" if lat is not None else ""
        status = "ok" + lat_str if ok else detail or "fail"
        print(f"  {name}: {status}")
    if data.get("error"):
        print(f"  Error: {data['error']}")

    return 0 if (tunnel_ok and all_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
