#!/usr/bin/env python3
"""
vendor_lookup_worker.py — resolve unknown merchants (v2 add-on).

Proposes candidate labels/locations only. Never writes sheet columns C/D.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AI_LAB_ROOT = Path(__file__).resolve().parents[1]
if str(AI_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_LAB_ROOT))

from brain.bank_vendor_cleaner.vendor_lookup import (
    lookup_vendor,
    promote_approved_cache_entries,
)


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Bank vendor lookup worker (no sheet writes)")
    parser.add_argument("--raw-input", required=True, help="Raw transaction string")
    parser.add_argument("--city-hint", default="")
    parser.add_argument("--state-hint", default="")
    parser.add_argument("--deterministic-label", default="")
    parser.add_argument("--deterministic-location", default="")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.add_argument("--promote-approved", action="store_true", help="Promote approved cache entries to alias map")
    args = parser.parse_args()

    if args.dry_run is None:
        args.dry_run = _env_bool("DRY_RUN", True)

    if args.promote_approved:
        promoted = promote_approved_cache_entries()
        print(json.dumps({"promoted": promoted}, indent=2))
        return 0

    if not _env_bool("VENDOR_LOOKUP_ENABLED", True):
        print(json.dumps({"error": "VENDOR_LOOKUP_ENABLED=false"}, indent=2))
        return 1

    result = lookup_vendor(
        args.raw_input,
        deterministic_label=args.deterministic_label,
        deterministic_location=args.deterministic_location,
        city_hint=args.city_hint,
        state_hint=args.state_hint,
        write_pending=not args.dry_run,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
