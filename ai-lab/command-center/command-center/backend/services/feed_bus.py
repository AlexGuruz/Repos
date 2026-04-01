"""
feed_bus.py — central pub/sub for all lab events.

Any service (NvidiaPoller, RepoWatcher, SupervisorBridge) calls
`await bus.publish(event, data)` and every connected WebSocket client
receives it instantly.
"""
import asyncio
import json
from datetime import datetime
from fastapi import WebSocket
from typing import Any

from services.observability import log_error, log_event_stream


class EventBus:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._history: list[dict] = []          # last 200 events for new connections
        self._history_limit = 200

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        # Replay recent history so the UI is immediately populated
        for msg in self._history[-50:]:
            try:
                await ws.send_text(json.dumps(msg, default=str))
            except Exception:
                break

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def publish(self, event: str, data: Any):
        msg = {
            "event": event,
            "data": data,
            "ts": datetime.utcnow().isoformat(),
        }
        log_event_stream(event, data)
        # Avoid replaying a pile of stale `hardware` snapshots to new WS clients; keep only the latest.
        if event == "hardware":
            self._history = [m for m in self._history if m.get("event") != "hardware"]
        self._history.append(msg)
        if len(self._history) > self._history_limit:
            self._history.pop(0)

        payload = json.dumps(msg, default=str)
        dead: list[WebSocket] = []
        for client in self._clients:
            try:
                await client.send_text(payload)
            except Exception:
                log_error("feed_bus", "websocket_send_failed", event=event)
                dead.append(client)
        for d in dead:
            self.disconnect(d)


bus = EventBus()
