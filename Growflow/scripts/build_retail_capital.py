"""
Build capital tab JSON from layer2 projection CSV.

Usage:
  PYTHONPATH=. python scripts/build_retail_capital.py
  PYTHONPATH=. python scripts/build_retail_capital.py --layer2-csv path/to/layer2.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.retail_dashboard.capital import (
    DEFAULT_CAPITAL_JSON,
    DEFAULT_LAYER2_CSV,
    build_capital,
    payload_to_dict,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build retail capital payload from layer2 CSV")
    ap.add_argument("--layer2-csv", default=str(DEFAULT_LAYER2_CSV))
    ap.add_argument("--out", default=str(DEFAULT_CAPITAL_JSON))
    args = ap.parse_args()

    payload = build_capital(layer2_path=args.layer2_csv)
    out = payload_to_dict(payload)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    ok = payload.meta.get("validation", {}).get("ok", False)
    print(
        f"Capital build {payload.meta.get('run_id')}: rows={payload.meta.get('row_count')} "
        f"funded={payload.meta.get('funded_row_count')} ok={ok}",
        flush=True,
    )
    print(f"Wrote {out_path}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
