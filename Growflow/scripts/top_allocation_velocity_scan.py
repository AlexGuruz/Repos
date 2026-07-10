"""Top 20 by allocated_cog_usd; flag high alloc + low velocity + long recovery."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"

# Heuristic thresholds (tune as needed)
LOW_VELOCITY_AUM = 10.0  # avg units/mo
LONG_RECOVERY_MO = 1.5  # months (above ~medium bucket for this dataset)
HIGH_ALLOC = 200.0  # USD — "high" slice of the tail


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    rows: list[dict] = []
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "brand": r["brand"],
                    "category": r["category"],
                    "allocated_cog_usd": float(r["allocated_cog_usd"]),
                    "avg_units_per_month": float(r["avg_units_per_month"])
                    if r.get("avg_units_per_month")
                    else None,
                    "months_to_recover_cog": float(r["months_to_recover_cog"])
                    if r.get("months_to_recover_cog")
                    else None,
                }
            )

    rows.sort(key=lambda x: -x["allocated_cog_usd"])

    print("Top 20 by allocated_cog_usd (highest first):")
    print("brand\tcategory\tallocated_cog_usd\tavg_units_per_month\tmonths_to_recover_cog")
    for r in rows[:20]:
        print(
            r["brand"],
            r["category"],
            f"{r['allocated_cog_usd']:.2f}",
            r["avg_units_per_month"] if r["avg_units_per_month"] is not None else "",
            r["months_to_recover_cog"] if r["months_to_recover_cog"] is not None else "",
            sep="\t",
        )

    print()
    print(
        f"Problem pattern scan: alloc>={HIGH_ALLOC} AND aum<{LOW_VELOCITY_AUM} "
        f"AND months>{LONG_RECOVERY_MO}"
    )
    hits = 0
    for r in rows:
        ac = r["allocated_cog_usd"]
        aum = r["avg_units_per_month"]
        mo = r["months_to_recover_cog"]
        if aum is None or mo is None:
            continue
        if ac >= HIGH_ALLOC and aum < LOW_VELOCITY_AUM and mo > LONG_RECOVERY_MO:
            hits += 1
            print(
                f"  TRAP: {r['brand'][:30]:30} {r['category'][:16]:16} "
                f"alloc=${ac:.2f} aum={aum:.2f} mo={mo:.2f}"
            )
    if hits == 0:
        print("  (none in this file with those thresholds)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
