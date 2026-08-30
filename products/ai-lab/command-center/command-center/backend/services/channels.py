"""
Multi-channel EventBus with isolated backpressure.

Named channels (telemetry / control / chat / ops) each own clients, queues,
history, and logging. A stuck telemetry client must never stall control.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import WebSocket

from services.observability import log_channel_event, log_error, log_metric

ChannelName = Literal["telemetry", "control", "chat", "ops"]

_WS_SEND_TIMEOUT_SEC = 0.5
_DEFAULT_HISTORY = {
    "telemetry": 5,
    "control": 100,
    "chat": 50,
    "ops": 80,
}
_DEFAULT_QUEUE = {
    "telemetry": 64,
    "control": 256,
    "chat": 128,
    "ops": 128,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_envelope(
    channel: ChannelName,
    event_type: str,
    payload: Any,
    *,
    source: str = "command-center",
    correlation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "channel": channel,
        "event_type": event_type,
        "schema_version": 1,
        "timestamp": _now(),
        "correlation_id": correlation_id,
        "source": source,
        "payload": payload,
        # Legacy keys for existing frontend demux
        "event": event_type,
        "data": payload,
        "ts": _now(),
    }


@dataclass
class ChannelMetrics:
    published: int = 0
    delivered: int = 0
    dropped: int = 0
    coalesced: int = 0
    send_failures: int = 0
    overload: int = 0
    connected_clients: int = 0
    max_queue_depth: int = 0


class Channel:
    """Isolated pub/sub lane with bounded outbound fan-out."""

    def __init__(
        self,
        name: ChannelName,
        *,
        queue_max: int | None = None,
        history_max: int | None = None,
        lossy: bool = False,
        coalesce_key: str | None = None,
    ):
        self.name = name
        self.lossy = lossy
        self.coalesce_key = coalesce_key
        self.queue_max = queue_max if queue_max is not None else _DEFAULT_QUEUE[name]
        self.history_max = history_max if history_max is not None else _DEFAULT_HISTORY[name]
        self._clients: list[WebSocket] = []
        self._history: deque[dict[str, Any]] = deque(maxlen=self.history_max)
        self._outbound: asyncio.Queue[dict[str, Any] | None] | None = None
        self._worker: asyncio.Task | None = None
        self._fanout_tasks: set[asyncio.Task] = set()
        self.metrics = ChannelMetrics()
        self._latest_by_key: dict[str, dict[str, Any]] = {}

    def _ensure_worker(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._outbound is None:
            self._outbound = asyncio.Queue(maxsize=self.queue_max)
        if self._worker is None or self._worker.done():
            self._worker = loop.create_task(self._drain_loop(), name=f"channel-{self.name}")

    async def start(self) -> None:
        self._ensure_worker()

    async def stop(self) -> None:
        if self._outbound is not None:
            try:
                self._outbound.put_nowait(None)
            except Exception:
                pass
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except Exception:
                pass
            self._worker = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.append(ws)
        self.metrics.connected_clients = len(self._clients)
        self._ensure_worker()
        for msg in list(self._history)[-20:]:
            ok = await self._send_one(ws, json.dumps(msg, default=str))
            if not ok:
                return

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        self.metrics.connected_clients = len(self._clients)

    async def publish(
        self,
        event_type: str,
        payload: Any,
        *,
        source: str = "command-center",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue envelope; returns immediately subject to channel policy."""
        env = make_envelope(
            self.name,
            event_type,
            payload,
            source=source,
            correlation_id=correlation_id,
        )
        self._ensure_worker()
        self.metrics.published += 1

        if self.lossy and self.coalesce_key:
            key = str((payload or {}).get(self.coalesce_key) if isinstance(payload, dict) else event_type)
            if key in self._latest_by_key:
                self.metrics.coalesced += 1
            self._latest_by_key[key] = env

        if self._outbound is None:
            # No running loop — history only (tests / sync contexts).
            self._history.append(env)
            log_channel_event(self.name, event_type, payload)
            return env

        try:
            if self.lossy:
                # Prefer drop-oldest / replace when full.
                while self._outbound.full():
                    try:
                        self._outbound.get_nowait()
                        self.metrics.dropped += 1
                    except asyncio.QueueEmpty:
                        break
                self._outbound.put_nowait(env)
            else:
                try:
                    self._outbound.put_nowait(env)
                except asyncio.QueueFull:
                    self.metrics.overload += 1
                    log_metric(
                        "channel_overload",
                        channel=self.name,
                        event_type=event_type,
                        depth=self._outbound.qsize(),
                    )
                    log_error(
                        "channels",
                        "control_channel_overload" if self.name == "control" else "channel_overload",
                        channel=self.name,
                        event_type=event_type,
                    )
                    # Control: do not silently drop — raise typed overload after logging.
                    if self.name == "control":
                        raise ChannelOverloadError(self.name, event_type)
                    self.metrics.dropped += 1
                    return env
        except ChannelOverloadError:
            raise
        except Exception as exc:
            log_error("channels", "publish_enqueue_failed", channel=self.name, error=str(exc)[:200])

        # History is updated at publish time so reconnect replay and tests are race-free.
        self._history.append(env)
        depth = self._outbound.qsize() if self._outbound else 0
        if depth > self.metrics.max_queue_depth:
            self.metrics.max_queue_depth = depth
        log_channel_event(self.name, event_type, payload)
        return env

    async def _drain_loop(self) -> None:
        assert self._outbound is not None
        while True:
            item = await self._outbound.get()
            if item is None:
                break
            # Coalesce: if lossy+key, deliver latest for that key.
            if self.lossy and self.coalesce_key and isinstance(item.get("payload"), dict):
                key = str(item["payload"].get(self.coalesce_key, item["event_type"]))
                latest = self._latest_by_key.get(key, item)
                item = latest
            await self._fanout(item)

    async def _fanout(self, env: dict[str, Any]) -> None:
        payload = json.dumps(env, default=str)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for client in list(self._clients):
            task = loop.create_task(self._send_tracked(client, payload))
            self._fanout_tasks.add(task)
            task.add_done_callback(self._fanout_tasks.discard)

    async def _send_tracked(self, client: WebSocket, payload: str) -> None:
        ok = await self._send_one(client, payload)
        if ok:
            self.metrics.delivered += 1

    async def _send_one(self, client: WebSocket, payload: str) -> bool:
        try:
            await asyncio.wait_for(client.send_text(payload), timeout=_WS_SEND_TIMEOUT_SEC)
            return True
        except Exception:
            self.metrics.send_failures += 1
            log_error("channels", "websocket_send_failed", channel=self.name)
            self.disconnect(client)
            return False

    def snapshot_metrics(self) -> dict[str, Any]:
        return {
            "channel": self.name,
            "published": self.metrics.published,
            "delivered": self.metrics.delivered,
            "dropped": self.metrics.dropped,
            "coalesced": self.metrics.coalesced,
            "send_failures": self.metrics.send_failures,
            "overload": self.metrics.overload,
            "connected_clients": self.metrics.connected_clients,
            "queue_depth": self._outbound.qsize() if self._outbound else 0,
            "max_queue_depth": self.metrics.max_queue_depth,
            "history_len": len(self._history),
        }


class ChannelOverloadError(Exception):
    def __init__(self, channel: str, event_type: str):
        super().__init__(f"Channel '{channel}' overloaded for event '{event_type}'")
        self.channel = channel
        self.event_type = event_type


# Compatibility routing (explicit prefixes; unknown → ops, never control).
_CONTROL_EXACT = frozenset(
    {
        "approval",
        "approval_resolution",
        "action",
        "permanent_rule",
        "permanent_rule_deleted",
    }
)
_TELEMETRY_EXACT = frozenset({"hardware", "hardware_alert"})
_CHAT_EXACT = frozenset({"chat"})


def route_event_to_channel(event: str) -> ChannelName:
    e = (event or "").strip()
    if e in _TELEMETRY_EXACT or e.startswith("hardware") or e.startswith("telemetry"):
        return "telemetry"
    if e in _CONTROL_EXACT or e.startswith("approval") or e.startswith("action"):
        return "control"
    if e in _CHAT_EXACT or e.startswith("chat"):
        return "chat"
    return "ops"


class ChannelHub:
    def __init__(self) -> None:
        self.telemetry = Channel("telemetry", lossy=True, coalesce_key="timestamp")
        self.control = Channel("control", lossy=False)
        self.chat = Channel("chat", lossy=False)
        self.ops = Channel("ops", lossy=True)
        self._shim_uses = 0

    def get(self, name: ChannelName) -> Channel:
        return getattr(self, name)

    async def start(self) -> None:
        for ch in (self.telemetry, self.control, self.chat, self.ops):
            await ch.start()

    async def stop(self) -> None:
        for ch in (self.telemetry, self.control, self.chat, self.ops):
            await ch.stop()

    async def publish(
        self,
        channel: ChannelName,
        event_type: str,
        payload: Any,
        *,
        source: str = "command-center",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        return await self.get(channel).publish(
            event_type,
            payload,
            source=source,
            correlation_id=correlation_id,
        )

    async def publish_compat(self, event: str, data: Any) -> dict[str, Any]:
        """Transitional bus.publish shim — instrumented; prefer explicit channel publish."""
        self._shim_uses += 1
        ch = route_event_to_channel(event)
        log_metric("bus_publish_shim", channel=ch, event=event, count=self._shim_uses)
        return await self.publish(ch, event, data, source="compat.bus.publish")

    def metrics(self) -> dict[str, Any]:
        return {
            "shim_uses": self._shim_uses,
            "channels": {
                name: self.get(name).snapshot_metrics()  # type: ignore[arg-type]
                for name in ("telemetry", "control", "chat", "ops")
            },
        }


channels = ChannelHub()
