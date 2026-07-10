#!/usr/bin/env python3
from __future__ import annotations

import uuid
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brain.orchestrator.main import run


def main() -> int:
    sessions = [f"live_{i}_{uuid.uuid4().hex[:6]}" for i in range(3)]
    prompts = [
        "hello",
        "what systems are active?",
        "what changed recently?",
        "summarize current repo status",
        "what should I work on today?",
        "what is Growflow status?",
        "what docs need cleanup?",
        "check worker health",
        "what is broken right now?",
        "what am I blocked on?",
        "summarize my ai-lab current state",
        "explain repo documentation status",
    ]
    count = 0
    for s in sessions:
        for p in prompts:
            run(p, session_id=s, request_id=f"live-{uuid.uuid4().hex[:10]}", write_response_trace=True)
            count += 1
    print(f"ran {count} turns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

