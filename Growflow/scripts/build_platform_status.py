#!/usr/bin/env python3
"""Build Growflow/data/platform_status_latest.json from local artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.platform_config import load_platform_config  # noqa: E402
from lib.platform_status import write_platform_status  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write platform_status_latest.json")
    ap.add_argument("--out", default=None, help="Override output path")
    args = ap.parse_args(argv)
    cfg = load_platform_config()
    out = Path(args.out) if args.out else None
    status = write_platform_status(out, cfg=cfg)
    print(json.dumps({"ok": status.get("overall_ok"), "breaches": status.get("slo_breaches"), "path": str(out or cfg.platform_status_json)}))
    return 0 if status.get("overall_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
