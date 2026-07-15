"""Minimal allowlisted Operator Desk tool for investor-demo qualification."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def main() -> int:
    payload = {
        "ok": True,
        "tool": "cc_investor_demo_ping",
        "marker": "QUAL_TOOL_OK",
        "ts": datetime.now(timezone.utc).isoformat(),
        "argv": sys.argv[1:],
    }
    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
