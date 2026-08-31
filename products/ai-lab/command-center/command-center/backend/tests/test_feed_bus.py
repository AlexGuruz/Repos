from __future__ import annotations

import asyncio
import json

from services.channels import ChannelHub
from services.feed_bus import EventBus, _WS_SEND_TIMEOUT_SEC


async def _publish_many(bus: EventBus, count: int):
    for i in range(count):
        await bus.publish("feed", {"detail": f"event-{i}"})
    if bus._fanout_tasks:
        await asyncio.gather(*list(bus._fanout_tasks), return_exceptions=True)


def test_feed_bus_ops_history_is_capped():
    hub = ChannelHub()
    bus = EventBus(hub)
    asyncio.run(_publish_many(bus, 205))

    assert len(hub.ops._history) == hub.ops.history_max
    assert hub.ops._history[0]["data"]["detail"] == f"event-{205 - hub.ops.history_max}"


def test_feed_bus_history_payload_shape():
    hub = ChannelHub()
    bus = EventBus(hub)
    asyncio.run(bus.publish("chat", {"role": "ai", "text": "hello"}))

    msg = hub.chat._history[-1]
    json.dumps(msg)
    assert msg["event"] == "chat"
    assert msg["data"]["text"] == "hello"


class _HangingWebSocket:
    def __init__(self):
        self.calls = 0

    async def send_text(self, _payload: str):
        self.calls += 1
        await asyncio.sleep(_WS_SEND_TIMEOUT_SEC + 2.0)


def test_feed_bus_publish_returns_before_stuck_client_finishes():
    hub = ChannelHub()
    bus = EventBus(hub)
    stuck = _HangingWebSocket()
    bus._clients.append(stuck)  # type: ignore[arg-type]

    async def _run():
        await asyncio.wait_for(
            bus.publish("approval_resolution", {"id": "approval-1", "resolution": "approved"}),
            timeout=0.5,
        )
        # Wait until send timeout disconnects the stuck client (or fan-out finishes).
        for _ in range(40):
            if stuck not in bus._clients:
                break
            if bus._fanout_tasks:
                await asyncio.gather(*list(bus._fanout_tasks), return_exceptions=True)
            else:
                await asyncio.sleep(0.05)

    asyncio.run(_run())
    assert stuck not in bus._clients
    assert stuck.calls == 1
