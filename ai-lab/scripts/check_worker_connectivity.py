#!/usr/bin/env python3
"""
Confirm the main rig can reach worker node(s) (Guru §26).
Run from ai-lab repo root with PYTHONPATH set so brain is importable.
Usage:
  python scripts/check_worker_connectivity.py
  python scripts/check_worker_connectivity.py --worker worker-rig-02
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add ai-lab root so we can import brain
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def check_one(worker_name: str) -> int:
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

    tunnel_ok = tunnel.get("likely_up", False)
    all_ok = data.get("all_ok", False)
    label = worker_name
    if tunnel_ok and all_ok:
        print(f"{label}: reachable (tunnel up, all services ok)")
    elif all_ok:
        print(f"{label}: partial (services ok; tunnel down or incomplete)")
    else:
        print(f"{label}: unreachable (tunnel or one or more services failed)")

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Check worker tunnel and service health")
    parser.add_argument(
        "--worker",
        default="worker-rig-01",
        help="Registry worker id (worker-rig-01 or worker-rig-02)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Check worker-rig-01 and worker-rig-02",
    )
    args = parser.parse_args()
    names = ["worker-rig-01", "worker-rig-02"] if args.all else [args.worker]
    worst = 0
    for name in names:
        worst = max(worst, check_one(name))
        if len(names) > 1:
            print()
    return worst


if __name__ == "__main__":
    sys.exit(main())
