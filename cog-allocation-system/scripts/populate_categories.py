#!/usr/bin/env python3
"""
Populate categories from sales CSVs → DROP DOWN HELPER column G (categories), column H (flags).
Recreated from COMMAND_REFERENCE.md.
"""
import csv
from pathlib import Path

def main():
    csv_dump = Path(__file__).parent.parent / "data" / "csv_dump"
    if not csv_dump.exists():
        print(f"[populate_categories] No csv_dump dir: {csv_dump}")
        return

    categories = set()
    for f in csv_dump.glob("*.csv"):
        with open(f, encoding="utf-8", errors="ignore") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                cat = row.get("Category", row.get("category", row.get("Type", "")))
                if cat:
                    categories.add(str(cat).strip())

    print(f"[populate_categories] Found {len(categories)} unique categories")
    for c in sorted(categories):
        print(f"  - {c}")

    # TODO: gspread write to DROP DOWN HELPER col G, H
    print("[populate_categories] Sheets write not yet implemented (need service_account)")

if __name__ == "__main__":
    main()
