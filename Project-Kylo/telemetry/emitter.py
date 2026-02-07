from __future__ import annotations
import json, os, sys, time, uuid
from typing import Dict, Any
from urllib.request import Request, urlopen
from urllib.error import URLError

SINK = os.getenv("TELEMETRY_SINK", "none").lower()  # "none" | "stdout" | "http"
WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "").strip()

def start_trace(kind: str, company_id: str) -> str:
    return f"{int(time.time())}-{uuid.uuid4().hex[:8]}-{company_id}-{kind}"

def emit(event_type: str, trace_id: str, step: str, payload: Dict[str, Any], level: str="info") -> None:
    if SINK == "none":
        return
    evt = {
        "ts": time.time(),
        "level": level,
        "trace_id": trace_id,
        "event_type": event_type,   # "mover" | "poster" | "importer"
        "step": step,               # "upsert_started" | "rows_enqueued" | ...
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
            # never break business logic
            return


