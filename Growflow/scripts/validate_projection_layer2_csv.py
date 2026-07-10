"""Validate projection_layer2_recovery.csv (allocation integrity + math checks). Stdlib only."""
from __future__ import annotations

import csv
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CSV = REPO / "data" / "projection_by_category_brand_layer2_recovery.csv"

# After regenerating the CSV, category mix shifts (e.g. Cartridges vs Disposables split).
ALLOWED_FOCUS_CATEGORIES = frozenset(
    {
        "Edibles",
        "Cartridges",
        "Disposables",
        "Prerolls",
        "Infused prerolls",
        "Topicals",
    }
)


def _f(x: str | None) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _i(x: str | None) -> int | None:
    if x is None or x == "":
        return None
    try:
        return int(float(x))
    except ValueError:
        return None


def describe(xs: list[float], name: str) -> None:
    if not xs:
        print(f"{name}: (no values)")
        return
    xs_sorted = sorted(xs)
    n = len(xs)
    mean = statistics.fmean(xs)
    print(f"{name} count    {n}")
    print(f"{name} mean     {mean:.12g}")
    print(f"{name} std      {statistics.pstdev(xs):.12g}" if n > 1 else f"{name} std      0")
    print(f"{name} min      {xs_sorted[0]:.12g}")
    print(f"{name} 25%      {xs_sorted[n // 4]:.12g}")
    print(f"{name} 50%      {xs_sorted[n // 2]:.12g}")
    print(f"{name} 75%      {xs_sorted[(3 * n) // 4]:.12g}")
    print(f"{name} max      {xs_sorted[-1]:.12g}")


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    raw = load_rows(path)
    fails: list[str] = []

    def ok(name: str, cond: bool, msg: str = "") -> None:
        st = "PASS" if cond else "FAIL"
        extra = f" {msg}" if msg else ""
        print(f"{name}: {st}{extra}")
        if not cond:
            fails.append(name)

    rows: list[dict] = []
    for r in raw:
        ac = _f(r.get("allocated_cog_usd"))
        rows.append(
            {
                "brand": r.get("brand") or "",
                "category": r.get("category") or "",
                "allocated_cog": ac,
                "trailing_units_sold": _i(r.get("trailing_units_sold")),
                "avg_units_per_month": _f(r.get("avg_units_per_month")),
                "avg_cog_per_unit": _f(r.get("avg_cog_per_unit")),
                "avg_retail_per_unit": _f(r.get("avg_retail_per_unit")),
                "units_from_allocation": _f(r.get("units_from_allocation")),
                "months_to_recover_cog": _f(r.get("months_to_recover_cog")),
                "projected_revenue_from_allocated_units_usd": _f(
                    r.get("projected_revenue_from_allocated_units_usd")
                ),
                "projected_gross_profit_usd": _f(r.get("projected_gross_profit_usd")),
                "allocation_efficiency": _f(r.get("allocation_efficiency")),
                "recovery_bucket": (r.get("recovery_bucket") or "").strip(),
            }
        )

    print("=" * 60)
    print("CHECK 1 - Total allocation == 18,000")
    total = sum(r["allocated_cog"] or 0.0 for r in rows)
    s = round(total, 2)
    ok("Check 1", abs(s - 18000.0) < 0.02, f"sum={s}")

    print("\nCHECK 2 - No missing allocations")
    na = sum(1 for r in rows if r["allocated_cog"] is None)
    ok("Check 2", na == 0, f"NA count={na}")

    print("\nCHECK 3 - No negative allocations")
    neg = sum(1 for r in rows if (r["allocated_cog"] or 0) < 0)
    ok("Check 3", neg == 0)

    print("\nCHECK 4 - units_from_allocation ~= allocated / avg_cog_per_unit")
    diff4: list[float] = []
    for r in rows:
        ac, cog, ufa = r["allocated_cog"], r["avg_cog_per_unit"], r["units_from_allocation"]
        if ac is None or cog is None or ufa is None or cog <= 0:
            continue
        calc = ac / cog
        diff4.append(abs(ufa - calc))
    describe(diff4, "abs_diff")
    mxd = max(diff4) if diff4 else 0.0
    ok("Check 4", mxd < 1e-5, f"max_abs_diff={mxd}")

    print("\nCHECK 5 - months_to_recover ~= units / avg_units_per_month")
    diff5: list[float] = []
    for r in rows:
        ufa, aum, mo = r["units_from_allocation"], r["avg_units_per_month"], r["months_to_recover_cog"]
        if ufa is None or aum is None or mo is None or aum <= 0:
            continue
        calc = ufa / aum
        diff5.append(abs(mo - calc))
    describe(diff5, "abs_diff")
    mxd5 = max(diff5) if diff5 else 0.0
    ok("Check 5", mxd5 < 1e-5, f"max_abs_diff={mxd5}")

    print("\nCHECK 6 - Revenue + GP")
    mx_rev = mx_gp = 0.0
    for r in rows:
        ufa, arpu, ac = r["units_from_allocation"], r["avg_retail_per_unit"], r["allocated_cog"]
        pr, pg = r["projected_revenue_from_allocated_units_usd"], r["projected_gross_profit_usd"]
        if ufa is None or arpu is None or ac is None or pr is None or pg is None:
            continue
        rev_c = ufa * arpu
        gp_c = rev_c - ac
        mx_rev = max(mx_rev, abs(pr - rev_c))
        mx_gp = max(mx_gp, abs(pg - gp_c))
    print(f"max |rev diff|: {mx_rev}")
    print(f"max |gp diff|: {mx_gp}")
    ok("Check 6", mx_rev < 1e-4 and mx_gp < 1e-4)

    print("\nCHECK 7 - trailing_units_sold <= 0 -> months NaN")
    z = [r for r in rows if (r["trailing_units_sold"] or 0) <= 0]
    print(f"rows with units<=0: {len(z)}")
    bad7 = any(r["months_to_recover_cog"] is not None and not math.isnan(r["months_to_recover_cog"]) for r in z)
    if z:
        for r in z:
            print(
                f"  {r['brand']}|{r['category']} units={r['trailing_units_sold']} "
                f"months={r['months_to_recover_cog']}"
            )
    ok("Check 7", not bad7 if z else True)

    print("\nCHECK 8 - avg_cog_per_unit <= 0 should not produce units")
    bad8 = False
    for r in rows:
        cog = r["avg_cog_per_unit"]
        if cog is not None and cog <= 0 and r["units_from_allocation"] is not None:
            bad8 = True
            break
    le0 = sum(1 for r in rows if r["avg_cog_per_unit"] is not None and r["avg_cog_per_unit"] <= 0)
    print(f"rows with avg_cog<=0: {le0}")
    ok("Check 8", not bad8)

    print("\nCHECK 9 - Slowest recovery (top 20)")
    with_mo = [r for r in rows if r["months_to_recover_cog"] is not None]
    with_mo.sort(key=lambda x: x["months_to_recover_cog"] or 0, reverse=True)
    for r in with_mo[:20]:
        print(
            f"  {r['brand'][:24]:24} {r['category'][:18]:18} "
            f"${r['allocated_cog'] or 0:>10.2f}  mo={r['months_to_recover_cog']:.4f}"
        )

    print("\nCHECK 10 - Category totals (allowed labels + sum to pool)")
    cat_sum: dict[str, float] = {}
    for r in rows:
        c = r["category"]
        cat_sum[c] = cat_sum.get(c, 0.0) + (r["allocated_cog"] or 0.0)
    unknown_cats = set(cat_sum) - ALLOWED_FOCUS_CATEGORIES
    for k in sorted(cat_sum, key=lambda x: -cat_sum[x]):
        print(f"  {k}: ${cat_sum[k]:,.2f}")
    ok("Check 10a", not unknown_cats, f"unknown categories: {sorted(unknown_cats)}")
    cat_total = round(sum(cat_sum.values()), 2)
    ok("Check 10b", abs(cat_total - 18000.0) < 0.02, f"sum categories={cat_total}")

    print("\nCHECK 11 - Brand totals (top samples; informational)")
    br_sum: dict[str, float] = {}
    for r in rows:
        b = r["brand"]
        br_sum[b] = br_sum.get(b, 0.0) + (r["allocated_cog"] or 0.0)
    print("\nTop 10 brands by allocated_cog:")
    for b, v in sorted(br_sum.items(), key=lambda x: -x[1])[:10]:
        print(f"  {b}: ${v:,.2f}")

    print("\nCHECK 12 - Top allocation vs velocity")
    rows_sorted = sorted(rows, key=lambda x: -(x["allocated_cog"] or 0))
    for r in rows_sorted[:15]:
        print(
            f"  {r['brand'][:22]:22} {r['category'][:16]:16} "
            f"${r['allocated_cog'] or 0:>9.2f}  aum={r['avg_units_per_month'] or 0:.2f}  "
            f"mo={r['months_to_recover_cog']}"
        )

    print("\nCHECK 13 - Best allocation_efficiency")
    eff_r = [r for r in rows if r["allocation_efficiency"] is not None]
    eff_r.sort(key=lambda x: x["allocation_efficiency"] or 0, reverse=True)
    for r in eff_r[:15]:
        print(f"  {r['brand'][:22]:22} {r['category'][:16]:16}  eff={r['allocation_efficiency']:.4f}")

    print("\nCHECK 14 - recovery_bucket counts")
    bc: dict[str, int] = {}
    for r in rows:
        k = r["recovery_bucket"] or "(empty)"
        bc[k] = bc.get(k, 0) + 1
    for k, v in sorted(bc.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    print("\nCHECK 15 - allocated_cog < 5")
    small = [r for r in rows if (r["allocated_cog"] or 0) < 5]
    print(f"rows: {len(small)}")
    for r in small[:30]:
        print(f"  {r['brand']}|{r['category']}: ${r['allocated_cog']:.2f}")

    print("\nCHECK 16 - Top 20: high $ vs units")
    for r in rows_sorted[:20]:
        print(
            f"  {r['brand'][:20]:20} {r['category'][:14]:14} "
            f"${r['allocated_cog'] or 0:>9.2f}  units={r['trailing_units_sold']}  "
            f"ufa={r['units_from_allocation']}"
        )

    neg_gp = sum(1 for r in rows if (r["projected_gross_profit_usd"] or 0) < 0)
    print(f"\nExtra: negative projected_gross_profit rows: {neg_gp}")

    print("\n" + "=" * 60)
    print("ONE SCREEN")
    print("TOTAL ALLOCATION:", round(total, 2))
    print("\nTOP 10 ALLOCATIONS:")
    for r in rows_sorted[:10]:
        print(
            f"  {r['brand'][:22]:22} {r['category'][:16]:16} "
            f"${r['allocated_cog'] or 0:>9.2f}  mo={r['months_to_recover_cog']}"
        )
    print("\nWORST RECOVERY:")
    for r in with_mo[:10]:
        print(
            f"  {r['brand'][:22]:22} {r['category'][:16]:16} "
            f"${r['allocated_cog'] or 0:>9.2f}  mo={r['months_to_recover_cog']:.4f}"
        )
    print("\nBEST EFFICIENCY:")
    for r in eff_r[:10]:
        print(f"  {r['brand'][:22]:22} {r['category'][:16]:16}  eff={r['allocation_efficiency']:.4f}")

    print("\n" + "=" * 60)
    if fails:
        print("OVERALL: FAIL -", ", ".join(fails))
        return 1
    print("OVERALL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
