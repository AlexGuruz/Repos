from pathlib import Path

p = Path(r"E:\Repos\products\ai-lab\command-center\command-center\backend\services\feed_bus.py")
p.write_text(
    '''"""
feed_bus.py — central pub/sub for all lab events.

Any service (NvidiaPoller, RepoWatcher, SupervisorBridge) calls
`await bus.publish(event, data)` and every connected WebSocket client
receives it instantly.

CRITICAL: Neither publish nor broadcast may stall the uvicorn event loop.
Stuck WebSocket clients previously caused Approve/Deny HTTP hangs.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from services.observability import log_error, log_event_stream

# Stuck TCP buffers can block send_text; bound each client send.
_WS_SEND_TIMEOUT_SEC = 0.5
_CONNECT_REPLAY_LIMIT = 20


class EventBus:
    def __init__(self):
        self._clients: list[WebSocket] = []
        self._history: list[dict] = []  # last 200 events for new connections
        self._history_limit = 200
        self._fanout_tasks: set[asyncio.Task] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients.append(ws)
        # Replay a small slice of non-hardware history only (fast connect).
        replay = [m for m in self._history if m.get("event") != "hardware"][-_CONNECT_REPLAY_LIMIT:]
        for msg in replay:
            ok = await self._send_one(ws, json.dumps(msg, default=str), event="history_replay")
            if not ok:
                return

    def disconnect(self, ws: WebSocket):
        if ws in self._clients:
            self._clients.remove(ws)

    async def publish(self, event: str, data: Any):
        """Record history and schedule fan-out; return without awaiting client sends."""
        msg = {
            "event": event,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        log_event_stream(event, data)
        # Avoid replaying a pile of stale `hardware` snapshots to new WS clients; keep only the latest.
        if event == "hardware":
            self._history = [m for m in self._history if m.get("event") != "hardware"]
        self._history.append(msg)
        if len(self._history) > self._history_limit:
            self._history.pop(0)

        payload = json.dumps(msg, default=str)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        # Per-client tasks — never gather/await fan-out on the publish path.
        for client in list(self._clients):
            task = loop.create_task(self._send_one(client, payload, event=event))
            self._fanout_tasks.add(task)
            task.add_done_callback(self._fanout_tasks.discard)

    async def _send_one(self, client: WebSocket, payload: str, *, event: str) -> bool:
        try:
            await asyncio.wait_for(client.send_text(payload), timeout=_WS_SEND_TIMEOUT_SEC)
            return True
        except Exception:
            log_error("feed_bus", "websocket_send_failed", event=event)
            self.disconnect(client)
            return False


bus = EventBus()
''',
    encoding="utf-8",
)
print("wrote", p, p.stat().st_size)
