#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    p = Path("state/ai_response_traces.jsonl")
    if not p.exists():
        print("trace file missing")
        return 1
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(r.get("request_id", "")).startswith("live-"):
            rows.append(r)
    print(f"live_rows={len(rows)}")
    if not rows:
        return 0

    slow = sorted(rows, key=lambda r: float(r.get("total_ms") or 0), reverse=True)[:8]
    print("\nTop slow paths:")
    for r in slow:
        print(
            f"- {r.get('user_message','')[:50]!r} total={r.get('total_ms')}ms first={r.get('first_token_ms')} "
            f"source={r.get('final_answer_source')} prepared={r.get('prepared_context_used')} "
            f"fallback={r.get('fallback_reason')} route={r.get('route_chosen')}"
        )

    by_source = Counter(str(r.get("final_answer_source") or "unknown") for r in rows)
    print("\nfinal_answer_source counts:", dict(by_source))

    prepared = [r for r in rows if r.get("prepared_context_used")]
    not_prepared = [r for r in rows if not r.get("prepared_context_used")]
    print(f"prepared_used={len(prepared)} not_prepared={len(not_prepared)}")

    weak = [
        r for r in prepared
        if (r.get("snapshot_stale") or (r.get("snapshot_types_used") and r.get("evidence_count", 0) <= 1))
    ]
    print(f"weak_snapshot_answers={len(weak)}")
    for r in weak[:6]:
        print(
            f"- weak {r.get('user_message','')[:48]!r} snapshots={r.get('snapshot_types_used')} "
            f"stale={r.get('snapshot_stale')} total={r.get('total_ms')}"
        )

    fast = [r for r in rows if float(r.get("total_ms") or 0) <= 300]
    fast_not_useful = []
    for r in fast:
        txt = (r.get("reply_preview") or "").lower()
        if "[orchestrator] intent:" in txt or "session-specific evidence" in txt:
            fast_not_useful.append(r)
    print(f"\nfast_answers={len(fast)} fast_not_useful={len(fast_not_useful)}")
    for r in fast_not_useful[:6]:
        print(f"- fast_not_useful {r.get('user_message','')[:48]!r} preview={r.get('reply_preview','')[:90]!r}")

    # snapshot usage heatmap
    snap_counts = Counter()
    for r in prepared:
        for s in (r.get("snapshot_types_used") or []):
            snap_counts[str(s)] += 1
    print("\nsnapshot_types_used counts:", dict(snap_counts))

    # slow fallthrough reasons
    falls = defaultdict(int)
    for r in rows:
        if not r.get("prepared_context_used"):
            falls[str(r.get("final_answer_source") or "unknown")] += 1
    print("non-prepared sources:", dict(falls))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

