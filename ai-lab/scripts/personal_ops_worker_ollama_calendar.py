#!/usr/bin/env python3
"""
Use Ollama on the worker to suggest calendar updates from a snapshot of primary events.

Flow: local Google Calendar read (your token) -> HTTP POST to worker Ollama /api/generate -> print model output.
Does NOT write to Google Calendar (review output first; use your existing stamp flow if you want writes).

Env:
  GOOGLE_CREDENTIALS_FILE, GOOGLE_CALENDAR_TOKEN_FILE — same as personal_ops_calendar_snapshot.py
  OLLAMA_HOST — default http://worker-node:11434 (LAN). Override if tunneling (127.0.0.1:11434).

  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

Example:
  set GOOGLE_CREDENTIALS_FILE=E:\\Repos\\ai-lab\\secrets\\client_secret_....json
  set GOOGLE_CALENDAR_TOKEN_FILE=E:\\Repos\\ai-lab\\secrets\\token.calendar.json
  set OLLAMA_HOST=http://worker-node:11434
  python scripts/personal_ops_worker_ollama_calendar.py --days 3 --model qwen2.5-coder:7b
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _ollama_base() -> str:
    import os

    raw = (os.environ.get("OLLAMA_HOST") or "http://worker-node:11434").strip().rstrip("/")
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "http://" + raw
    return raw


def _ollama_generate(base: str, model: str, prompt: str, timeout_sec: float = 300.0) -> str:
    url = f"{base.rstrip('/')}/api/generate"
    body = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama unreachable at {base}: {e}") from e
    return str(data.get("response") or "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Worker Ollama + Google Calendar snapshot (suggest-only).")
    ap.add_argument("--days", type=int, default=5)
    ap.add_argument("--calendar-id", default="primary")
    ap.add_argument("--model", default="qwen2.5-coder:7b")
    ap.add_argument(
        "--max-events",
        type=int,
        default=25,
        help="Cap events sent to the model (most recent window first).",
    )
    args = ap.parse_args()

    from lib.google_calendar_client import get_calendar_service, list_events

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=args.days)
    tfmt = "%Y-%m-%dT%H:%M:%SZ"
    svc = get_calendar_service()
    events = list_events(
        svc,
        args.calendar_id,
        time_min=now.strftime(tfmt),
        time_max=end.strftime(tfmt),
        max_results=max(50, args.max_events + 10),
    )[: args.max_events]

    slim: list[dict] = []
    for ev in events:
        st = ev.get("start", {})
        start = st.get("dateTime") or st.get("date") or ""
        desc = (ev.get("description") or "")[:900]
        slim.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": start,
                "lane_hint": _lane_from_description(ev.get("description") or ""),
                "description_excerpt": desc,
            }
        )

    events_json = json.dumps(slim, indent=2)
    prompt = f"""You help update a personal Google Calendar that uses a fixed convention.
Each event may include a description whose first line looks like:
  SOURCE: <email> · AI-generated · <lane>
where <lane> is e.g. personal, bills, etc.

Here are upcoming events (JSON). IDs are Google Calendar instance ids — do not invent ids.

EVENTS_JSON:
{events_json}

TASK:
Return ONLY a JSON array (no markdown fences, no commentary). Each element must be an object with keys:
  "event_id" (string, must match an id from EVENTS_JSON),
  "suggested_append" (string, 1-4 sentences to append at the END of that event's description; plain text, no HTML),
  "rationale" (string, one short line).

If you have nothing useful for an event, omit it from the array. Prefer fewer, higher-quality suggestions.
Do not repeat the entire description; only append-style updates (progress, check-ins, gentle nudges aligned with lane).
"""

    base = _ollama_base()
    sys.stderr.write(f"Ollama: {base} model={args.model}\n")
    raw = _ollama_generate(base, args.model, prompt)
    raw = raw.strip()
    # Strip accidental ```json fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```\s*$", "", raw)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        print("\n---\n(Model output was not valid JSON.)", file=sys.stderr)
        return 1
    print(json.dumps(parsed, indent=2))
    return 0


def _lane_from_description(desc: str) -> str:
    for line in desc.splitlines():
        if "SOURCE:" in line and "·" in line:
            parts = [p.strip() for p in line.split("·")]
            if len(parts) >= 3:
                return parts[-1].strip()
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
