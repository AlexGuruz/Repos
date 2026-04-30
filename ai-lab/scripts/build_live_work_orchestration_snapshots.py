#!/usr/bin/env python3
"""
Build Phase 9 live work orchestration snapshots (read-only).

Writes under ai-lab/state/live_work_orchestration/

Usage (from ai-lab root):
  python scripts/build_live_work_orchestration_snapshots.py
  python scripts/build_live_work_orchestration_snapshots.py --preview
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build live work orchestration snapshots (Phase 9).")
    parser.add_argument("--preview", action="store_true", help="Print compact daily plan preview to stdout")
    args = parser.parse_args()

    from brain.live_work_orchestration.builders import build_all_live_work_snapshots
    from brain.live_work_orchestration.compiler import compile_daily_plan_preview

    build_all_live_work_snapshots()
    print(f"Wrote snapshots under {ROOT / 'state' / 'live_work_orchestration'}")
    if args.preview:
        prev = compile_daily_plan_preview()
        print("")
        print("=== Daily plan preview (read-only) ===")
        for key in (
            "today",
            "before_shift",
            "during_shift",
            "after_shift",
            "top_priorities",
            "constraints",
            "risks_to_watch",
            "a_good_day_looks_like",
        ):
            print(f"\n## {key.replace('_', ' ').title()}\n{prev.get(key, '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
