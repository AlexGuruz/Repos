"""Print worst months_to_recover rows and flag capital traps."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"


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
                    "allocation_efficiency": float(r["allocation_efficiency"])
                    if r.get("allocation_efficiency")
                    else None,
                }
            )

    rows.sort(
        key=lambda x: (x["months_to_recover_cog"] is None, -(x["months_to_recover_cog"] or -1.0))
    )

    cols = [
        "brand",
        "category",
        "allocated_cog_usd",
        "avg_units_per_month",
        "months_to_recover_cog",
        "allocation_efficiency",
    ]
    print("Top 15 by months_to_recover_cog (worst first):")
    for c in cols:
        print(c, end="\t")
    print()
    for r in rows[:15]:
        print(
            r["brand"],
            r["category"],
            f"{r['allocated_cog_usd']:.2f}",
            r["avg_units_per_month"] if r["avg_units_per_month"] is not None else "",
            r["months_to_recover_cog"] if r["months_to_recover_cog"] is not None else "",
            r["allocation_efficiency"] if r["allocation_efficiency"] is not None else "",
            sep="\t",
        )

    print()
    print(
        "Capital trap scan: non-trivial alloc ($100+) AND "
        "(months>6 OR avg_units/mo<10 OR efficiency<2)"
    )
    for r in rows:
        mo = r["months_to_recover_cog"]
        aum = r["avg_units_per_month"]
        ac = r["allocated_cog_usd"]
        eff = r["allocation_efficiency"]
        if ac < 100:
            continue
        reasons: list[str] = []
        if mo is not None and mo > 6:
            reasons.append(f"mo>{6}")
        if aum is not None and aum < 10:
            reasons.append("aum<10")
        if eff is not None and eff < 2:
            reasons.append("eff<2")
        if reasons:
            print(
                f"  {r['brand'][:28]:28} {r['category'][:18]:18} "
                f"alloc=${ac:.2f} aum={aum if aum is not None else 'n/a'} "
                f"mo={mo if mo is not None else 'n/a'} eff={eff if eff is not None else 'n/a'} "
                f"-> {', '.join(reasons)}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
