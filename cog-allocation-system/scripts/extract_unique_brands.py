#!/usr/bin/env python3
"""
Extract unique brands from sales CSV files → Google Sheet DROP DOWN HELPER column E.
Recreated from COMMAND_REFERENCE.md.
"""
import argparse
import csv
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="Extract unique brands from CSVs")
    ap.add_argument("--dry-run", action="store_true", help="Preview only, no Sheets write")
    ap.add_argument("--remove-excluded-brands", action="store_true",
                    help="Remove brands if ALL categories excluded (column H)")
    args = ap.parse_args()

    csv_dump = Path(__file__).parent.parent / "data" / "csv_dump"
    if not csv_dump.exists():
        print(f"[extract_unique_brands] No csv_dump dir: {csv_dump}")
        return

    brands = set()
    for f in csv_dump.glob("*.csv"):
        with open(f, encoding="utf-8", errors="ignore") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                # Assume brand in common column names
                for key in ("Brand", "brand", "Product", "product", "Item"):
                    if key in row and row[key]:
                        brands.add(str(row[key]).strip())
                        break

    print(f"[extract_unique_brands] Found {len(brands)} unique brands")
    for b in sorted(brands):
        print(f"  - {b}")

    if args.dry_run:
        print("[extract_unique_brands] Dry run - not writing to Sheets")
        return

    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from lib.sheets_helper import write_brands_to_drop_down_helper
        if write_brands_to_drop_down_helper(list(brands)):
            print("[extract_unique_brands] Wrote brands to DROP DOWN HELPER")
        else:
            print("[extract_unique_brands] Add config.yaml (spreadsheet_id) + service_account.json")
    except Exception as e:
        print(f"[extract_unique_brands] Sheets write failed: {e}")


if __name__ == "__main__":
    main()
