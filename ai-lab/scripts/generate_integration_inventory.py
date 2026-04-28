#!/usr/bin/env python3
"""CLI entry for Phase 4 integration inventory (JSON + markdown)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from brain.integration_inventory.integration_inventory_generator import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
