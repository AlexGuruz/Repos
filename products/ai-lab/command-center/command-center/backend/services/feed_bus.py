"""
feed_bus.py — compatibility facade over ChannelHub.

Prefer:
    from services.channels import channels
    await channels.control.publish("approval", {...})

Legacy:
    await bus.publish(event, data)  # routes via compatibility map + metrics
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket

from services.channels import ChannelHub, channels, _WS_SEND_TIMEOUT_SEC
from services.observability import log_metric


class EventBus:
    """Deprecated singleton facade over ChannelHub."""

    def __init__(self, hub: ChannelHub | None = None) -> None:
        # Production uses shared hub; tests may pass a fresh ChannelHub().
        self._hub = hub if hub is not None else ChannelHub()

    async def connect(self, ws: WebSocket) -> None:
        """Deprecated /ws/events: multiplex control + ops + chat (never telemetry)."""
        await ws.accept()
        log_metric("ws_events_deprecated_connect", count=1)
        for ch in (self._hub.control, self._hub.ops, self._hub.chat):
            if ws not in ch._clients:
                ch._clients.append(ws)
                ch.metrics.connected_clients = len(ch._clients)
            ch._ensure_worker()
        # Bounded replay — no telemetry
        for ch in (self._hub.control, self._hub.ops, self._hub.chat):
            for msg in list(ch._history)[-10:]:
                try:
                    await ch._send_one(ws, json.dumps(msg, default=str))
                except Exception:
                    return
        await self._hub.start()

    def disconnect(self, ws: WebSocket) -> None:
        self._hub.control.disconnect(ws)
        self._hub.ops.disconnect(ws)
        self._hub.chat.disconnect(ws)

    async def publish(self, event: str, data: Any):
        return await self._hub.publish_compat(event, data)

    @property
    def _clients(self):
        """For tests that inject stuck sockets onto control."""
        return self._hub.control._clients

    @property
    def _history(self):
        return list(self._hub.control._history) + list(self._hub.ops._history) + list(self._hub.chat._history)

    @property
    def _fanout_tasks(self):
        tasks = set()
        for ch in (self._hub.telemetry, self._hub.control, self._hub.chat, self._hub.ops):
            tasks |= ch._fanout_tasks
        return tasks


bus = EventBus(channels)

__all__ = ["EventBus", "bus", "_WS_SEND_TIMEOUT_SEC"]
