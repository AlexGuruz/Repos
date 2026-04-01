from __future__ import annotations

import json

from services.feed_bus import EventBus


async def _publish_many(bus: EventBus, count: int):
    for i in range(count):
        await bus.publish("feed", {"detail": f"event-{i}"})


def test_feed_bus_history_is_capped():
    bus = EventBus()
    import asyncio

    asyncio.run(_publish_many(bus, 205))

    assert len(bus._history) == 200
    assert bus._history[0]["data"]["detail"] == "event-5"


def test_feed_bus_history_payload_shape():
    bus = EventBus()
    import asyncio

    asyncio.run(bus.publish("chat", {"role": "ai", "text": "hello"}))

    msg = bus._history[-1]
    json.dumps(msg)
    assert msg["event"] == "chat"
    assert msg["data"]["text"] == "hello"
