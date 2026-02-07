#!/usr/bin/env python3
"""
Calculate daily COG per brand from sales CSV → NUGZ COG / PUFFIN COG / EMPIRE COG sheets.
Recreated from COMMAND_REFERENCE.md.
"""
import argparse
import csv
from pathlib import Path
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser(description="Calculate daily COG from sales CSVs")
    ap.add_argument("--csv-files", nargs="+", required=True, help="Paths to sales CSV files")
    ap.add_argument("--dry-run", action="store_true", help="Preview only, no Sheets write")
    args = ap.parse_args()

    daily_by_brand = defaultdict(lambda: defaultdict(float))

    for path in args.csv_files:
        p = Path(path)
        if not p.exists():
            print(f"[calculate_daily_cog] Skip (not found): {p}")
            continue
        with open(p, encoding="utf-8", errors="ignore") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                # TODO: Parse date, brand, revenue/cost columns from actual OrderItems format
                # Placeholder: accumulate by date+brand
                date = row.get("Date", row.get("date", ""))
                brand = row.get("Brand", row.get("brand", row.get("Product", "Unknown")))
                amt = float(row.get("Amount", row.get("amount", row.get("Revenue", 0))) or 0)
                if date and brand:
                    daily_by_brand[date][brand] += amt

    print(f"[calculate_daily_cog] Processed {len(daily_by_brand)} dates")
    for d in sorted(daily_by_brand.keys())[:5]:
        print(f"  {d}: {dict(daily_by_brand[d])}")

    if args.dry_run:
        print("[calculate_daily_cog] Dry run - not writing to Sheets")
        return

    # TODO: gspread write to NUGZ COG (or company-specific COG sheet)
    print("[calculate_daily_cog] Sheets write not yet implemented (need service_account + layout_map)")

if __name__ == "__main__":
    main()
