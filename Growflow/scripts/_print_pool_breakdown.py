"""One-off: print brand pool breakdown sorted by pool $."""
import csv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
p = root / "data" / "brand_merit_12m.csv"
rows = list(csv.DictReader(p.open(encoding="utf-8")))
for r in rows:
    r["_pool"] = float(r["pool_allocation_usd"])
rows.sort(key=lambda r: r["_pool"], reverse=True)
s = sum(r["_pool"] for r in rows)
print(f"brands={len(rows)} sum_pool={s:.2f}\n")
for r in rows:
    print(f"{r['brand']}\t{r['_pool']:.2f}")
