"""
QUAL Stage 7 load harness — temporary, stoppable, telemetry-client + control resolve timing.
Does not monkeypatch production channel publishers.
Usage:
  python evidence/qual_stage7_load_harness.py --seconds 20 --out <dir>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import urllib.request
from pathlib import Path

try:
    import websockets
except ImportError:
    websockets = None


BASE = "http://127.0.0.1:8000"


def http_json(path: str, method: str = "GET", body: dict | None = None, timeout: float = 30.0):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def pct(samples: list[float], p: float) -> float:
    if not samples:
        return float("nan")
    s = sorted(samples)
    k = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


async def slow_telemetry_client(stop: asyncio.Event, lag_s: float = 0.2):
    """Intentionally slow /ws/telemetry consumer (drain with lag)."""
    if websockets is None:
        return {"error": "websockets not installed"}
    uri = "ws://127.0.0.1:8000/ws/telemetry"
    n = 0
    try:
        async with websockets.connect(uri, max_size=8_000_000) as ws:
            while not stop.is_set():
                try:
                    await asyncio.wait_for(ws.recv(), timeout=0.5)
                    n += 1
                    await asyncio.sleep(lag_s)
                except asyncio.TimeoutError:
                    continue
    except Exception as exc:
        return {"error": str(exc), "recv": n}
    return {"recv": n}


async def main_async(seconds: float, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    _, before = http_json("/api/channels/metrics")
    out_dir.joinpath("stage7_metrics_before.json").write_text(json.dumps(before, indent=2), encoding="utf-8")

    stop = asyncio.Event()
    slow_task = asyncio.create_task(slow_telemetry_client(stop, lag_s=0.25))

    control_samples: list[float] = []
    resolve_samples: list[float] = []
    t_end = time.perf_counter() + seconds
    mid_snap = None
    i = 0
    while time.perf_counter() < t_end:
        # proxy for control publish latency: resolve missing id (still hits control path timing in logs)
        # Prefer list_approvals + health as control/ops pressure; also call permanent list.
        t0 = time.perf_counter()
        try:
            http_json("/api/approvals/permanent")
            http_json("/api/health")
            http_json("/api/channels/metrics")
            code, body = http_json(
                "/api/approvals/resolve",
                method="POST",
                body={"id": f"approval-missing-qual-{i}", "resolution": "denied"},
            )
            dt = (time.perf_counter() - t0) * 1000
            resolve_samples.append(dt)
            # When found=false, publish may not run; still records API latency under load
            control_samples.append(dt)
        except Exception as exc:
            resolve_samples.append(-1)
            out_dir.joinpath("stage7_error.txt").write_text(str(exc), encoding="utf-8")
        i += 1
        if mid_snap is None and time.perf_counter() > t_end - seconds / 2:
            _, mid_snap = http_json("/api/channels/metrics")
            out_dir.joinpath("stage7_metrics_during.json").write_text(json.dumps(mid_snap, indent=2), encoding="utf-8")
        await asyncio.sleep(0.05)

    stop.set()
    slow = await slow_task
    _, after = http_json("/api/channels/metrics")
    out_dir.joinpath("stage7_metrics_after.json").write_text(json.dumps(after, indent=2), encoding="utf-8")

    good = [x for x in resolve_samples if x >= 0]
    summary = {
        "seconds": seconds,
        "iterations": i,
        "slow_telemetry_client": slow,
        "resolve_or_miss_ms": {
            "n": len(good),
            "p50": pct(good, 50),
            "p95": pct(good, 95),
            "p99": pct(good, 99),
            "max": max(good) if good else None,
            "mean": statistics.mean(good) if good else None,
        },
        "note": (
            "Live control-publish p95 should be taken from api_requests resolve_timing/"
            "resolve_result publish_ms under concurrent Approve when available; "
            "this harness stresses API+slow telemetry client while poller publishes."
        ),
        "channels_before": before.get("channels"),
        "channels_after": after.get("channels"),
        "tunnel_after": after.get("tunnel"),
    }
    out_dir.joinpath("stage7_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary["resolve_or_miss_ms"], indent=2))
    print("slow", slow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    asyncio.run(main_async(args.seconds, args.out))


if __name__ == "__main__":
    main()
