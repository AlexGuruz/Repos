#!/usr/bin/env python3
"""
Run orchestrator prompts with AI_LAB_ORCH_NO_LLM=1 (no LM Studio calls) and print a markdown table.

Usage (from ai-lab root):
  set AI_LAB_ORCH_NO_LLM=1
  python scripts/benchmark_ai_response.py > docs/AI_RESPONSE_BENCHMARKS.md
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["AI_LAB_ORCH_NO_LLM"] = "1"
os.environ.setdefault("AI_LAB_LLM_SKIP_MODEL_LIST_PROBE", "1")

from brain.orchestrator.main import run  # noqa: E402

PROMPTS = [
    "hello",
    "what systems are active?",
    "summarize my ai-lab current state",
    "what should I work on today?",
    "check worker health",
    "what changed recently in Growflow?",
    "explain repo documentation status",
]


def _route_from_reply(p: str, reply: str) -> str:
    if "Ready" in reply or "I can help" in reply:
        return "greeting_shortcircuit"
    if "Worker **" in reply or "worker" in reply.lower() and "tunnel" in reply.lower():
        return "worker_health"
    if "Operations registry" in reply or "## Systems" in reply:
        return "ops_evidence_or_summary"
    if "session-specific evidence" in reply.lower():
        return "insufficient_evidence"
    if "[Orchestrator]" in reply:
        return "orchestrator_fallback"
    return "answer_path"


def main() -> int:
    rows = []
    for p in PROMPTS:
        sid = f"bench_{abs(hash(p)) % 100000}"
        t0 = time.perf_counter()
        out = run(
            p,
            llm_base_url="",
            llm_model="",
            session_id=sid,
            write_response_trace=False,
        )
        total_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        reply = out.get("reply") or ""
        rows.append(
            {
                "prompt": p.replace("|", "\\|"),
                "total_ms": total_ms,
                "route_guess": _route_from_reply(p, reply),
                "reply_preview": (reply[:120].replace("\n", " ") + ("…" if len(reply) > 120 else "")),
            }
        )

    print("# AI response benchmarks (local, no LLM)")
    print("")
    print("Environment: `AI_LAB_ORCH_NO_LLM=1`, `AI_LAB_LLM_SKIP_MODEL_LIST_PROBE=1`, empty `llm_base_url` in `run()`.")
    print("This measures **orchestrator + routing + evidence** latency without LM Studio.")
    print("")
    print("| Prompt | Total ms | Route (heuristic) | Reply preview |")
    print("|--------|----------|-------------------|---------------|")
    for r in rows:
        print(f"| {r['prompt']} | {r['total_ms']} | {r['route_guess']} | {r['reply_preview']} |")
    print("")
    print("For **first-token** and **per-stage** timings, see `state/ai_response_traces.jsonl` with `write_response_trace=True` (Command Center chat).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
