from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

# Add parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.rules_promoter.service import promote


def main() -> int:
    ap = argparse.ArgumentParser(description="Promote approved pending rules to active for companies")
    ap.add_argument("--cids", help="Comma-separated companies (default: all in DSN map)")
    ap.add_argument("--dsn-map", help="JSON map company_id->DSN (overrides KYLO_DB_DSN_MAP)")
    ap.add_argument("--dsn-map-file", help="Path to JSON file with company_id->DSN mapping")
    ap.add_argument("--global-dsn", help="Global DSN for snapshots (optional; if absent, will still bump versions table if reachable)")
    args = ap.parse_args()

    dsn_map_env = None
    if args.dsn_map_file and os.path.exists(args.dsn_map_file):
        with open(args.dsn_map_file, "r", encoding="utf-8") as f:
            dsn_map_env = f.read()
    dsn_map_env = dsn_map_env or args.dsn_map or os.environ.get("KYLO_DB_DSN_MAP")
    if not dsn_map_env:
        print("KYLO_DB_DSN_MAP not set and --dsn-map not provided")
        return 2
    company_dsn_map: Dict[str, str] = json.loads(dsn_map_env)
    companies: Optional[List[str]] = None
    if args.cids:
        companies = [c.strip() for c in args.cids.split(",") if c.strip()]

    global_dsn = args.global_dsn or os.environ.get("KYLO_DB_GLOBAL") or os.environ.get("DATABASE_URL_POOL")
    if not global_dsn:
        # Use an impossible DSN placeholder; the promote function handles errors and reports per-company
        global_dsn = "postgresql://invalid/"

    res = promote(global_dsn, company_dsn_map, companies)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


