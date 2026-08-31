"""
Build consignment tab JSON from consignment.db (read-only snapshot).

Usage:
  PYTHONPATH=. python scripts/build_retail_consignment.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.retail_dashboard.consignment import DEFAULT_CONSIGNMENT_JSON, build_consignment, payload_to_dict


def main() -> int:
    ap = argparse.ArgumentParser(description="Build retail consignment JSON from SQLite")
    ap.add_argument("--db-path", default=None)
    ap.add_argument("--out", default=str(DEFAULT_CONSIGNMENT_JSON))
    args = ap.parse_args()

    payload = build_consignment(db_path=args.db_path)
    out = payload_to_dict(payload)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    ok = payload.meta.get("validation", {}).get("ok", False)
    print(
        f"Consignment build {payload.meta.get('run_id')}: "
        f"transfers={len(payload.active_transfers)} ledger={len(payload.daily_ledger)} ok={ok}",
        flush=True,
    )
    print(f"Wrote {out_path}", flush=True)
    return 0 if ok or not payload.meta.get("source_exists") else 1


if __name__ == "__main__":
    raise SystemExit(main())
