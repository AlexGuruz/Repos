#!/usr/bin/env python3
"""
Automated monthly execution: run pipeline, validation (inside pipeline), category suggestions, archive outputs.
Run from Growflow repo root: python -m company_bi.scripts.monthly_run [--months 12]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
COMPANY_BI = Path(__file__).resolve().parent.parent
OUTPUT = COMPANY_BI / "output"
ARCHIVE_BASE = COMPANY_BI / "archive"

CSV_NAMES = [
    "dashboard",
    "anomalies",
    "margin",
    "reconciliation",
    "expense_category",
    "labor",
    "inventory_analysis",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly BI run: pipeline, suggestions, archive")
    ap.add_argument("--months", type=int, default=12, help="Months of data to fetch")
    ap.add_argument("--skip-suggestions", action="store_true", help="Do not run category rule suggestions")
    args = ap.parse_args()

    archive_dir = ARCHIVE_BASE / date.today().strftime("%Y-%m")
    archive_dir.mkdir(parents=True, exist_ok=True)

    print("Running pipeline (--no-sheets)...", flush=True)
    r = subprocess.run(
        [sys.executable, "-m", "company_bi.run_pipeline", "--no-sheets", f"--months={args.months}"],
        cwd=str(ROOT),
        timeout=600,
    )
    if r.returncode != 0:
        print(f"Pipeline failed with exit code {r.returncode}", file=sys.stderr, flush=True)
        return r.returncode

    print("Archiving outputs...", flush=True)
    for name in CSV_NAMES:
        src = OUTPUT / f"{name}.csv"
        if src.exists():
            shutil.copy2(src, archive_dir / f"{name}.csv")
    if (OUTPUT / "category_rule_suggestions.csv").exists():
        shutil.copy2(OUTPUT / "category_rule_suggestions.csv", archive_dir / "category_rule_suggestions.csv")

    if not args.skip_suggestions:
        print("Running category rule suggestions...", flush=True)
        subprocess.run(
            [sys.executable, "-m", "company_bi.scripts.suggest_category_rules", f"--months={args.months}"],
            cwd=str(ROOT),
            timeout=120,
        )
        if (OUTPUT / "category_rule_suggestions.csv").exists():
            shutil.copy2(OUTPUT / "category_rule_suggestions.csv", archive_dir / "category_rule_suggestions.csv")

    print(f"Done. Outputs in {OUTPUT}; archive in {archive_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
