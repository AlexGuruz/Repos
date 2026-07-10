#!/usr/bin/env python3
"""
Run Phase 12 GitHub PR/issue ingestion (read-only).

Usage (from ai-lab root):
  python scripts/ingest_github_activity.py
  python scripts/ingest_github_activity.py --rebuild-daily-progress
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_repo_snapshot_if_present() -> dict | None:
    p = ROOT / "state" / "live_work_orchestration" / "ingestion" / "repo_activity_snapshot.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest GitHub PR/issue activity into live work snapshots (read-only).")
    parser.add_argument(
        "--rebuild-daily-progress",
        action="store_true",
        help="Rebuild daily_progress_snapshot after GitHub ingestion.",
    )
    args = parser.parse_args()

    from brain.live_work_orchestration.ingestion.github_activity import build_github_activity_snapshot

    repo_snap = _load_repo_snapshot_if_present()
    snap = build_github_activity_snapshot(repo_activity_snapshot=repo_snap)
    data = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    summary = data.get("correlation_summary") if isinstance(data.get("correlation_summary"), dict) else {}
    print("=== GitHub Activity Ingestion (read-only) ===")
    print(
        "prs={prs} issues={issues} feature_states={feature_states} "
        "matched={matched} local_without_pr={local_without_pr} blocked_prs={blocked}".format(
            prs=len(data.get("prs") or []),
            issues=len(data.get("issues") or []),
            feature_states=len(data.get("feature_states") or []),
            matched=summary.get("local_with_pr_match", 0),
            local_without_pr=summary.get("local_without_pr", 0),
            blocked=summary.get("blocked_prs", 0),
        )
    )
    if args.rebuild_daily_progress:
        from brain.live_work_orchestration.builders import build_daily_progress_snapshot

        dp = build_daily_progress_snapshot()
        events = ((dp.get("data") or {}).get("events") or [])
        print(f"daily_progress_snapshot rebuilt: events={len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
