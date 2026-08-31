"""
Load isolation: ≥50 Hz fake telemetry + stuck client → control publish stays fast.
Target: control publish p95 < 500 ms (approval resolve path proxy).
"""
from __future__ import annotations

import asyncio
import statistics
import time

from services.channels import ChannelHub


def test_control_publish_p95_under_telemetry_flood():
    hub = ChannelHub()

    class _Stuck:
        async def send_text(self, _payload: str):
            await asyncio.sleep(60)

    async def _run():
        await hub.start()
        hub.telemetry._clients.append(_Stuck())  # type: ignore[arg-type]

        stop = asyncio.Event()

        async def telemetry_flood():
            n = 0
            while not stop.is_set():
                await hub.telemetry.publish("hardware", {"timestamp": str(n), "n": n})
                n += 1
                await asyncio.sleep(0.02)  # 50 Hz

        flood = asyncio.create_task(telemetry_flood())
        await asyncio.sleep(0.1)
        samples: list[float] = []
        for i in range(30):
            t0 = time.perf_counter()
            await hub.control.publish("approval_resolution", {"id": f"APR-{i}", "resolution": "approved"})
            samples.append((time.perf_counter() - t0) * 1000)
            await asyncio.sleep(0.01)
        stop.set()
        await flood
        samples.sort()
        p95 = samples[int(len(samples) * 0.95) - 1]
        p50 = statistics.median(samples)
        print(f"control_publish_ms p50={p50:.2f} p95={p95:.2f} max={max(samples):.2f}")
        print(f"telemetry metrics={hub.telemetry.snapshot_metrics()}")
        assert p95 < 500.0, f"control publish p95 {p95:.1f}ms exceeded 500ms"
        assert hub.control.metrics.published == 30

    asyncio.run(_run())
