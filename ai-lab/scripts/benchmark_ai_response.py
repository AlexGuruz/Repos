#!/usr/bin/env python3
"""
Run orchestrator prompts with AI_LAB_ORCH_NO_LLM=1 (no LM Studio calls) and print a markdown table to stdout.

By default this does **not** modify `docs/AI_RESPONSE_BENCHMARKS.md` (avoids noisy git churn on every run).
To refresh the auto snapshot block in that file—for prompt-set changes, structural updates, or milestone
snapshots—set `AI_LAB_BENCH_WRITE_DOC=1` when running.

Usage (from ai-lab root):
  set AI_LAB_ORCH_NO_LLM=1
  python scripts/benchmark_ai_response.py
  # optional: redirect stdout yourself, or milestone snapshot:
  set AI_LAB_BENCH_WRITE_DOC=1
  python scripts/benchmark_ai_response.py
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["AI_LAB_ORCH_NO_LLM"] = "1"
os.environ.setdefault("AI_LAB_LLM_SKIP_MODEL_LIST_PROBE", "1")

from brain.orchestrator.main import run  # noqa: E402
from brain.orchestrator.response_trace import trace_file_path  # noqa: E402

PROMPTS = [
    "hello",
    "what systems are active?",
    "what changed recently?",
    "summarize my ai-lab current state",
    "what should I work on today?",
    "summarize current repo status",
    "open project agenda",
    "check worker health",
    "what is Growflow status?",
    "what docs need cleanup?",
    "make a docs cleanup plan",
    "prepare a docs update proposal",
    "which README needs updating?",
    "what changed recently in Growflow?",
    "explain repo documentation status",
    # Phase 7 — documentation policy / validation paraphrases
    "what is wrong with this README?",
    "validate repo documentation",
    "what sections are missing in docs?",
    "improve this repo documentation",
    # Phase 8 — repo-level docs maintainer
    "score repo documentation",
    "give ai-lab docs a grade",
    "make a repo docs workplan",
    "check docs consistency",
    "create a batch docs proposal",
    "what docs should be updated together?",
    # Phase 5 — prepared-context selection paraphrases
    "anything broken?",
    "status of the lab",
    "which repos need cleanup?",
    "what are my next actions?",
    "plan my day",
    "is ollama up on the worker?",
    "transfer receipt status",
    "business automation status",
    "who won the super bowl in 2024?",
]

BENCHMARK_DOC = ROOT / "docs" / "AI_RESPONSE_BENCHMARKS.md"
AUTO_START = "<!-- AUTO_BENCHMARK_SNAPSHOT_START -->"
AUTO_END = "<!-- AUTO_BENCHMARK_SNAPSHOT_END -->"


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


def _load_trace_by_request_id(request_id: str) -> dict:
    tf = trace_file_path()
    if not tf.exists():
        return {}
    try:
        lines = tf.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return {}
    for line in reversed(lines[-2000:]):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("request_id") == request_id:
            return rec
    return {}


def _is_useful(reply: str, final_answer_source: str = "") -> bool:
    low = reply.lower()
    if "[orchestrator] intent:" in low:
        return False
    if "session-specific evidence" in low and "what you can do next" not in low:
        return False
    if (final_answer_source or "").strip().lower() == "unknown":
        return False
    return True


def _is_wrong_refusal(prompt: str, reply: str) -> bool:
    low = reply.lower()
    p = prompt.lower()
    if "[orchestrator] intent:" in low:
        return True
    if "session-specific evidence" in low and not any(k in p for k in ("worker", "sales", "exact", "specific")):
        return True
    return False


def _build_snapshot_markdown(rows: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        AUTO_START,
        "## Auto Benchmark Snapshot",
        "",
        f"Updated: `{ts}`",
        "",
        "| Prompt | First token ms | Total ms | Useful | Wrong refusal | Evidence used | Worker used |",
        "|--------|----------------|----------|--------|---------------|---------------|-------------|",
    ]
    for r in rows:
        ft = r["first_token_ms"] if r["first_token_ms"] is not None else r["total_ms"]
        lines.append(
            f"| {r['prompt']} | {ft} | {r['total_ms']} | {r['useful']} | "
            f"{r['wrong_refusal']} | {r['evidence_used']} | {r['worker_used']} |"
        )
    lines.extend(
        [
            "",
            "_Generated by `scripts/benchmark_ai_response.py`._",
            AUTO_END,
            "",
        ]
    )
    return "\n".join(lines)


def _update_benchmark_doc(rows: list[dict]) -> None:
    snapshot = _build_snapshot_markdown(rows)
    if BENCHMARK_DOC.exists():
        existing = BENCHMARK_DOC.read_text(encoding="utf-8", errors="replace")
    else:
        existing = "# AI response benchmarks\n\n"
    if AUTO_START in existing and AUTO_END in existing:
        start = existing.index(AUTO_START)
        end = existing.index(AUTO_END) + len(AUTO_END)
        updated = existing[:start] + snapshot.strip() + existing[end:]
    else:
        if not existing.endswith("\n"):
            existing += "\n"
        updated = existing + "\n" + snapshot
    BENCHMARK_DOC.write_text(updated, encoding="utf-8")


def main() -> int:
    rows = []
    for p in PROMPTS:
        sid = f"bench_{abs(hash(p)) % 100000}"
        rid = f"bench-{uuid.uuid4().hex[:10]}"
        t0 = time.perf_counter()
        out = run(
            p,
            llm_base_url="",
            llm_model="",
            session_id=sid,
            request_id=rid,
            write_response_trace=True,
        )
        total_ms = round((time.perf_counter() - t0) * 1000.0, 1)
        reply = out.get("reply") or ""
        tr = _load_trace_by_request_id(rid)
        sources = tr.get("sources_used") or []
        fallback_reason = tr.get("fallback_reason")
        rows.append(
            {
                "prompt": p.replace("|", "\\|"),
                "total_ms": total_ms,
                "first_token_ms": tr.get("first_token_ms"),
                "route_guess": _route_from_reply(p, reply),
                "model": tr.get("model") or "(none)",
                "worker_used": bool(tr.get("worker_used")),
                "evidence_used": len(sources),
                "wrong_refusal": "yes" if _is_wrong_refusal(p, reply) else "no",
                "useful": "yes" if _is_useful(reply, str(tr.get("final_answer_source") or "")) else "no",
                "fallback_reason": fallback_reason or "",
                "reply_preview": (reply[:120].replace("\n", " ") + ("…" if len(reply) > 120 else "")),
            }
        )

    print("# AI response benchmarks (local, no LLM)")
    print("")
    print("Environment: `AI_LAB_ORCH_NO_LLM=1`, `AI_LAB_LLM_SKIP_MODEL_LIST_PROBE=1`, empty `llm_base_url` in `run()`.")
    print("This measures **orchestrator + routing + evidence** latency without LM Studio.")
    print("")
    print("| Prompt | First token ms | Total ms | Route (heuristic) | Useful | Wrong refusal | Evidence used | Worker used | Reply preview |")
    print("|--------|----------------|----------|-------------------|--------|---------------|---------------|-------------|---------------|")
    for r in rows:
        ft = r["first_token_ms"] if r["first_token_ms"] is not None else r["total_ms"]
        print(
            f"| {r['prompt']} | {ft} | {r['total_ms']} | {r['route_guess']} | "
            f"{r['useful']} | {r['wrong_refusal']} | {r['evidence_used']} | {r['worker_used']} | {r['reply_preview']} |"
        )
    print("")
    print("For **first-token** and **per-stage** timings, see `state/ai_response_traces.jsonl` with `write_response_trace=True` (Command Center chat).")
    # Practical regression probe: warm greeting should stay fast.
    warm_sid = f"bench_hello_warm_{uuid.uuid4().hex[:6]}"
    _ = run("hello", llm_base_url="", llm_model="", session_id=warm_sid, write_response_trace=False)
    warm_ms: list[float] = []
    for _ in range(3):
        t0 = time.perf_counter()
        _ = run("hello", llm_base_url="", llm_model="", session_id=warm_sid, write_response_trace=False)
        warm_ms.append(round((time.perf_counter() - t0) * 1000.0, 2))
    warm_median = sorted(warm_ms)[1]
    print(f"Warm greeting latency probe (ms): {warm_ms} median={warm_median}")
    if os.environ.get("AI_LAB_BENCH_ASSERT", "").strip() in ("1", "true", "yes"):
        assert warm_median < 300.0, f"warm greeting median too slow: {warm_median}ms"
    write_bench_doc = os.environ.get("AI_LAB_BENCH_WRITE_DOC", "").strip().lower() in ("1", "true", "yes")
    if write_bench_doc:
        _update_benchmark_doc(rows)
        print(f"Wrote auto snapshot block to: {BENCHMARK_DOC}")
    else:
        print(
            f"Skipped writing {BENCHMARK_DOC.name} (set AI_LAB_BENCH_WRITE_DOC=1 to refresh the committed snapshot)."
        )

    if os.environ.get("AI_LAB_DOC_BENCH", "").strip() in ("1", "true", "yes"):
        from brain.repo_doc_validation import validate_readme
        from brain.repo_docs_maintainer import build_docs_cleanup_plan, create_docs_update_proposal

        readme = ROOT / "README.md"
        t0 = time.perf_counter()
        if readme.is_file():
            for _ in range(5):
                validate_readme(readme)
        v_ms = round((time.perf_counter() - t0) * 1000.0 / max(5, 1), 2)
        t1 = time.perf_counter()
        for _ in range(3):
            build_docs_cleanup_plan(message="bench", max_items=10)
        p_ms = round((time.perf_counter() - t1) * 1000.0 / 3.0, 2)
        t2 = time.perf_counter()
        for _ in range(3):
            create_docs_update_proposal(message="bench")
        prop_ms = round((time.perf_counter() - t2) * 1000.0 / 3.0, 2)
        print("")
        print("Phase 7 doc policy microbench (AI_LAB_DOC_BENCH=1, mean ms over repeats):")
        print(f"- validate_readme(README): {v_ms}ms (target <300ms per call)")
        print(f"- build_docs_cleanup_plan: {p_ms}ms (target <1000ms)")
        print(f"- create_docs_update_proposal: {prop_ms}ms (target <2000ms)")

        from brain.repo_docs_repo_level import (
            assess_repo_documentation,
            build_repo_docs_workplan,
            check_repo_docs_consistency,
            create_repo_docs_batch_proposal,
        )

        t3 = time.perf_counter()
        for _ in range(3):
            assess_repo_documentation(ROOT)
        s_ms = round((time.perf_counter() - t3) * 1000.0 / 3.0, 2)
        t4 = time.perf_counter()
        for _ in range(3):
            check_repo_docs_consistency(ROOT)
        c_ms = round((time.perf_counter() - t4) * 1000.0 / 3.0, 2)
        t5 = time.perf_counter()
        for _ in range(3):
            build_repo_docs_workplan(ROOT)
        w_ms = round((time.perf_counter() - t5) * 1000.0 / 3.0, 2)
        t6 = time.perf_counter()
        for _ in range(3):
            create_repo_docs_batch_proposal(ROOT)
        b_ms = round((time.perf_counter() - t6) * 1000.0 / 3.0, 2)
        print("Phase 8 repo-level microbench (same env, mean ms / 3 runs on ai-lab root):")
        print(f"- assess_repo_documentation: {s_ms}ms (target <500ms)")
        print(f"- check_repo_docs_consistency: {c_ms}ms (target <1000ms)")
        print(f"- build_repo_docs_workplan: {w_ms}ms (target <1000ms)")
        print(f"- create_repo_docs_batch_proposal: {b_ms}ms (target <2000ms)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
