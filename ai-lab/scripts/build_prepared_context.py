#!/usr/bin/env python3
"""
Build prepared context snapshots for fast orchestrator answers.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from brain.prepared_context.builders import build_all_snapshots, build_snapshot  # noqa: E402
from brain.prepared_context.store import SNAPSHOT_NAMES, write_index, write_snapshot  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--snapshot",
        default="all",
        choices=["all", *SNAPSHOT_NAMES],
        help="Which snapshot to refresh",
    )
    args = ap.parse_args()
    snaps = build_all_snapshots() if args.snapshot == "all" else [build_snapshot(args.snapshot)]
    rows = []
    for s in snaps:
        p = write_snapshot(s)
        rows.append(
            {
                "snapshot_type": s.snapshot_type,
                "generated_at": s.generated_at,
                "freshness_seconds": s.freshness_seconds,
                "stale": s.stale,
                "confidence": s.confidence,
                "path": str(p),
                "errors": s.errors,
                "summary_short": s.summary_short,
            }
        )
        print(f"built: {s.snapshot_type} -> {p}")
    # refresh index with all available snapshots in state
    from brain.prepared_context.store import load_snapshot

    merged: list[dict] = []
    for name in SNAPSHOT_NAMES:
        data = load_snapshot(name)
        if not data:
            continue
        merged.append(
            {
                "snapshot_type": name,
                "generated_at": data.get("generated_at"),
                "freshness_seconds": data.get("freshness_seconds"),
                "stale": data.get("stale"),
                "confidence": data.get("confidence"),
                "errors": data.get("errors", []),
                "summary_short": data.get("summary_short", ""),
            }
        )
    write_index(merged)
    print("index refreshed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

