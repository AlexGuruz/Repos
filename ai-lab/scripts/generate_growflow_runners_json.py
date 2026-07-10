#!/usr/bin/env python3
"""Regenerate state/integration_inventory/growflow_runners.json from Growflow tree."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from brain.integration_inventory.growflow_classify import build_inventory  # noqa: E402


def main() -> int:
    growflow = Path(__file__).resolve().parents[2] / "Growflow"
    if not growflow.is_dir():
        print("Growflow repo not found next to ai-lab; set path manually.", file=sys.stderr)
        return 1
    inv = build_inventory(growflow)
    out_dir = _root / "state" / "integration_inventory"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "growflow_runners.json"
    out_path.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({len(inv['scripts'])} scripts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
