"""Sections 3-7: efficiency vs allocation, recovery buckets, slow capital, units, category means."""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"


def load(path: Path) -> list[dict]:
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
                    "units_from_allocation": float(r["units_from_allocation"])
                    if r.get("units_from_allocation")
                    else None,
                    "recovery_bucket": (r.get("recovery_bucket") or "").strip() or "(empty)",
                }
            )
    return rows


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    rows = load(path)
    total_pool = sum(r["allocated_cog_usd"] for r in rows)

    # --- 3. Top 20 efficiency ---
    eff_sorted = sorted(
        rows,
        key=lambda x: (x["allocation_efficiency"] is None, -(x["allocation_efficiency"] or -1.0)),
    )
    print("=" * 72)
    print("3. Top 20 by allocation_efficiency (desc)")
    print("brand\tcategory\tefficiency\tallocated_cog_usd\tmonths_to_recover")
    for r in eff_sorted[:20]:
        print(
            r["brand"][:28],
            r["category"][:14],
            f"{r['allocation_efficiency']:.4f}" if r["allocation_efficiency"] is not None else "",
            f"{r['allocated_cog_usd']:.2f}",
            f"{r['months_to_recover_cog']:.4f}" if r["months_to_recover_cog"] is not None else "",
            sep="\t",
        )

    top_eff = eff_sorted[:10]
    bot_eff = sorted(
        [x for x in rows if x["allocation_efficiency"] is not None],
        key=lambda x: x["allocation_efficiency"] or 0.0,
    )[:10]

    print()
    print("3b. Misalignment check (heuristic)")
    hi_alloc = 200.0
    lo_alloc = 50.0
    hi_eff_top_alloc = sum(1 for r in top_eff if r["allocated_cog_usd"] >= hi_alloc)
    lo_eff_hi_alloc = sum(1 for r in bot_eff if r["allocated_cog_usd"] >= hi_alloc)
    print(
        f"  Among top-10 efficiency: count with alloc>={hi_alloc:.0f}: {hi_eff_top_alloc} "
        f"(high efficiency + tiny $ is common / noise)"
    )
    print(
        f"  Among bottom-10 efficiency: count with alloc>={hi_alloc:.0f}: {lo_eff_hi_alloc} "
        f"(low efficiency + big $ => suboptimal if frequent)"
    )
    print("  Bottom 10 by efficiency:")
    for r in bot_eff:
        print(
            f"    {r['brand'][:26]:26} {r['category'][:12]:12} "
            f"eff={r['allocation_efficiency']:.3f} alloc=${r['allocated_cog_usd']:.2f}"
        )

    # --- 4. recovery_bucket counts ---
    print()
    print("=" * 72)
    print('4. recovery_bucket value_counts()')
    bc: dict[str, int] = defaultdict(int)
    for r in rows:
        bc[r["recovery_bucket"]] += 1
    for k, v in sorted(bc.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    # --- 5. Slow capital (>4 months) ---
    print()
    print("=" * 72)
    print("5. Slow rows: months_to_recover_cog > 4")
    slow = [r for r in rows if r["months_to_recover_cog"] is not None and r["months_to_recover_cog"] > 4]
    slow_sum = sum(r["allocated_cog_usd"] for r in slow)
    pct = 100.0 * slow_sum / total_pool if total_pool else 0.0
    print(f"  Rows: {len(slow)}")
    print(f"  Sum allocated_cog_usd: ${slow_sum:,.2f} ({pct:.1f}% of ${total_pool:,.2f} pool)")
    if pct > 40:
        interp = ">40% in slow — heavy concern"
    elif pct > 30:
        interp = "30-40% — borderline / review"
    elif pct > 20:
        interp = "20-30% — watch"
    else:
        interp = "<20% — healthy by your rule of thumb"
    print(f"  Interpretation: {interp}")
    for r in sorted(slow, key=lambda x: -x["allocated_cog_usd"])[:15]:
        print(
            f"    {r['brand'][:24]:24} {r['category'][:14]:14} "
            f"${r['allocated_cog_usd']:.2f} mo={r['months_to_recover_cog']:.1f}"
        )

    # --- 6. Top units_from_allocation ---
    print()
    print("=" * 72)
    print("6. Top 15 by units_from_allocation (desc)")
    u_sorted = sorted(
        rows,
        key=lambda x: (x["units_from_allocation"] is None, -(x["units_from_allocation"] or -1.0)),
    )
    print("brand\tcategory\tunits_from_allocation\tallocated_cog_usd\tavg_cog_per_unit (implied)")
    # implied avg cog = alloc / units
    for r in u_sorted[:15]:
        ufa = r["units_from_allocation"]
        ac = r["allocated_cog_usd"]
        implied = ac / ufa if ufa and ufa > 0 else None
        print(
            r["brand"][:26],
            r["category"][:12],
            f"{ufa:.2f}" if ufa is not None else "",
            f"{ac:.2f}",
            f"{implied:.4f}" if implied is not None else "",
            sep="\t",
        )

    # --- 7. Category means ---
    print()
    print("=" * 72)
    print("7. groupby(category): mean(months_to_recover_cog), mean(allocation_efficiency)")
    by_cat: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for r in rows:
        if r["months_to_recover_cog"] is None or r["allocation_efficiency"] is None:
            continue
        by_cat[r["category"]].append((r["months_to_recover_cog"], r["allocation_efficiency"]))

    print("category\tmean_months\tmean_efficiency\tn_rows")
    for cat in sorted(by_cat.keys()):
        pairs = by_cat[cat]
        n = len(pairs)
        mm = sum(p[0] for p in pairs) / n
        me = sum(p[1] for p in pairs) / n
        print(f"{cat}\t{mm:.4f}\t{me:.4f}\t{n}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
