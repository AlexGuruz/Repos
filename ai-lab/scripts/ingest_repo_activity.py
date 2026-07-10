#!/usr/bin/env python3
"""
Run Phase 11 local repo activity ingestion (read-only metadata lane).

Usage (from ai-lab root):
  python scripts/ingest_repo_activity.py
  python scripts/ingest_repo_activity.py --rebuild-daily-progress
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest local repo activity into live work snapshots (read-only).")
    parser.add_argument(
        "--rebuild-daily-progress",
        action="store_true",
        help="Rebuild daily_progress_snapshot after ingestion completes.",
    )
    args = parser.parse_args()

    from brain.live_work_orchestration.ingestion.repo_activity import build_repo_activity_snapshot

    snap = build_repo_activity_snapshot()
    data = snap.get("data") if isinstance(snap.get("data"), dict) else {}
    summary = data.get("summary") if isinstance(data, dict) else {}
    print("=== Repo Activity Ingestion (read-only) ===")
    print(
        "repos_scanned={repos_scanned} repos_with_activity={repos_with_activity} "
        "high_intensity_repos={high_intensity_repos} errors={errors}".format(
            repos_scanned=summary.get("repos_scanned", 0),
            repos_with_activity=summary.get("repos_with_activity", 0),
            high_intensity_repos=summary.get("high_intensity_repos", 0),
            errors=len(snap.get("errors") or []),
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
