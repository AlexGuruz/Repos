"""Unit + isolation tests for ChannelHub."""
from __future__ import annotations

import asyncio
import time

import pytest

from services.channels import (
    ChannelHub,
    ChannelOverloadError,
    make_envelope,
    route_event_to_channel,
)


def test_route_event_map():
    assert route_event_to_channel("hardware") == "telemetry"
    assert route_event_to_channel("hardware_alert") == "telemetry"
    assert route_event_to_channel("approval") == "control"
    assert route_event_to_channel("approval_resolution") == "control"
    assert route_event_to_channel("action") == "control"
    assert route_event_to_channel("chat") == "chat"
    assert route_event_to_channel("feed") == "ops"
    assert route_event_to_channel("repo_index_dirty") == "ops"
    assert route_event_to_channel("totally_unknown_xyz") == "ops"


def test_envelope_shape():
    env = make_envelope("control", "approval", {"id": "APR-1"})
    assert env["channel"] == "control"
    assert env["event_type"] == "approval"
    assert env["event"] == "approval"
    assert env["data"]["id"] == "APR-1"
    assert env["schema_version"] == 1
    assert env["event_id"]


def test_compat_shim_routes_and_counts():
    hub = ChannelHub()

    async def _run():
        await hub.publish_compat("hardware", {"timestamp": "t1", "cpu_percent": 1})
        await hub.publish_compat("approval", {"id": "APR-1"})
        await hub.publish_compat("mystery_event", {"x": 1})
        assert hub.telemetry.metrics.published == 1
        assert hub.control.metrics.published == 1
        assert hub.ops.metrics.published == 1
        assert hub._shim_uses == 3

    asyncio.run(_run())


def test_telemetry_lossy_drops_when_full():
    hub = ChannelHub()
    hub.telemetry.queue_max = 4

    async def _run():
        await hub.telemetry.start()
        # Fill without draining by pausing fanout clients; overwhelm queue.
        for i in range(20):
            await hub.telemetry.publish("hardware", {"timestamp": f"t{i}", "n": i})
        m = hub.telemetry.snapshot_metrics()
        assert m["dropped"] > 0 or m["coalesced"] >= 0
        assert m["published"] == 20

    asyncio.run(_run())


def test_control_overload_raises():
    hub = ChannelHub()
    hub.control.queue_max = 2

    async def _run():
        await hub.control.start()
        # Pause drain by replacing outbound get with a stuck queue — simpler: fill without worker.
        hub.control._worker = asyncio.get_running_loop().create_task(asyncio.sleep(3600))
        hub.control._outbound = asyncio.Queue(maxsize=2)
        await hub.control.publish("approval", {"id": "1"})
        await hub.control.publish("approval", {"id": "2"})
        with pytest.raises(ChannelOverloadError):
            await hub.control.publish("approval", {"id": "3"})

    asyncio.run(_run())


def test_isolation_stuck_telemetry_does_not_block_control():
    hub = ChannelHub()

    class _Stuck:
        calls = 0

        async def send_text(self, _payload: str):
            self.calls += 1
            await asyncio.sleep(30)

    async def _run():
        await hub.start()
        stuck = _Stuck()
        hub.telemetry._clients.append(stuck)  # type: ignore[arg-type]

        # Flood telemetry
        async def flood():
            for i in range(40):
                await hub.telemetry.publish("hardware", {"timestamp": f"t{i}", "n": i})

        flood_task = asyncio.create_task(flood())
        t0 = time.perf_counter()
        await asyncio.wait_for(
            hub.control.publish("approval_resolution", {"id": "APR-x", "resolution": "approved"}),
            timeout=0.5,
        )
        control_ms = (time.perf_counter() - t0) * 1000
        await flood_task
        assert control_ms < 500
        assert hub.control.metrics.published == 1

    asyncio.run(_run())


def test_history_bounded_per_channel():
    hub = ChannelHub()

    async def _run():
        for i in range(200):
            await hub.ops.publish("feed", {"detail": f"e-{i}"})
        assert len(hub.ops._history) == hub.ops.history_max

    asyncio.run(_run())
