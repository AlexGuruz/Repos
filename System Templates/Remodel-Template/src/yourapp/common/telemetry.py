"""
Telemetry emitter for event tracking.

Generic telemetry system that supports multiple output sinks:
- stdout: JSON lines for log aggregation
- http: POST to webhook URL
- none: disabled
"""
from __future__ import annotations
import json
import os
import sys
import time
import uuid
from typing import Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

SINK = os.getenv("TELEMETRY_SINK", "none").lower()  # "none" | "stdout" | "http"
WEBHOOK_URL = os.getenv("TELEMETRY_WEBHOOK_URL", "").strip()


def start_trace(kind: str, entity_id: str) -> str:
    """
    Start a new trace for tracking.
    
    Args:
        kind: Type of trace (e.g., "processor", "worker")
        entity_id: Entity identifier (e.g., company_id, batch_id)
        
    Returns:
        Trace ID string
    """
    return f"{int(time.time())}-{uuid.uuid4().hex[:8]}-{entity_id}-{kind}"


def emit(event_type: str, trace_id: str, step: str, payload: Dict[str, Any], level: str = "info") -> None:
    """
    Emit a telemetry event.
    
    Args:
        event_type: Type of event (e.g., "processor", "worker", "api")
        trace_id: Trace ID from start_trace()
        step: Step name (e.g., "started", "completed", "failed")
        payload: Event payload dictionary
        level: Log level (info, warning, error)
    """
    if SINK == "none":
        return
    
    evt = {
        "ts": time.time(),
        "level": level,
        "trace_id": trace_id,
        "event_type": event_type,
        "step": step,
        "payload": payload,
    }
    
    if SINK == "stdout":
        sys.stdout.write(json.dumps(evt, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return
    
    if SINK == "http" and WEBHOOK_URL:
        try:
            data = json.dumps(evt).encode("utf-8")
            req = Request(WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=5):
                pass
        except URLError:
            # Never break business logic
            return
