"""
Shim: company_bi.run_pipeline was never restored in-repo.

Use:
  PYTHONPATH=. python scripts/build_company_bi_report.py
  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db
"""
from __future__ import annotations

import sys


def main() -> int:
    sys.stderr.write(
        "company_bi.run_pipeline is retired.\n"
        "Use:\n"
        "  PYTHONPATH=. python scripts/build_company_bi_report.py\n"
        "  PYTHONPATH=. python -m company_bi.scripts.build_sheets_transactions_db\n"
        "See docs/GROWFLOW_OPS_PLATFORM.md\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
