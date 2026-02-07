from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.ops.dashboard import write_dashboard_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kylo ops dashboard (local rollup)")
    p.add_argument(
        "--out",
        default=str(Path(".kylo") / "ops" / "dashboard.json"),
        help="Output JSON path (default: .kylo/ops/dashboard.json)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out = write_dashboard_json(Path(args.out))
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

