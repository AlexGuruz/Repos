"""
Export transfer package lines with receipt timestamps for cohort / sell-through metrics.

Writes **JSONL** (one JSON object per line) for easy append + Kylo / warehouse loaders.

Default output: ``data/transfer_receipt_units.jsonl`` (gitignored). Override with ``--out``.

Examples::

  PYTHONPATH=. python scripts/export_transfer_receipt_units.py
  PYTHONPATH=. python scripts/export_transfer_receipt_units.py --transfers 100 --out exports/receipts.jsonl
  PYTHONPATH=. python scripts/export_transfer_receipt_units.py --status Accepted --transfers 8
  # Next transfers after the most recent 8 (9th onward), append to same JSONL:
  PYTHONPATH=. python scripts/export_transfer_receipt_units.py --skip-transfers 8 --transfers 20 --append

Environment / credentials: same as other Growflow scripts (``GROWFLOW_RETAIL_ORG``,
``GROWFLOW_CREDENTIALS_PATH`` / ``E:/secrets/gcp/growflowapi.txt``, ``GROWFLOW_ACCESS_TOKEN``).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.transfer_receipt_export import fetch_transfer_receipt_rows, write_jsonl


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default=str(_root / "data" / "transfer_receipt_units.jsonl"),
        help="Output JSONL path (default: data/transfer_receipt_units.jsonl)",
    )
    ap.add_argument(
        "--transfers",
        type=int,
        default=50,
        metavar="N",
        help="Number of transfers to include after --skip-transfers (by ReceivedAt desc)",
    )
    ap.add_argument(
        "--skip-transfers",
        type=int,
        default=0,
        metavar="K",
        help="Skip the K most recent transfers (e.g. 8 to exclude the batch you already exported)",
    )
    ap.add_argument(
        "--status",
        default="Accepted",
        help='Transfer Status filter (default: "Accepted")',
    )
    ap.add_argument(
        "--print-counts",
        action="store_true",
        help="Print transfer id + line count + units to stderr after export",
    )
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to --out instead of overwriting (JSONL only)",
    )
    args = ap.parse_args()
    cp = _credentials_path()
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("No credentials: set GROWFLOW_CREDENTIALS_PATH or GROWFLOW_ACCESS_TOKEN", file=sys.stderr)
        sys.exit(1)
    rows = fetch_transfer_receipt_rows(
        first=args.transfers,
        skip=args.skip_transfers,
        status=args.status,
        credentials_path=cp,
    )
    out = Path(args.out)
    write_jsonl(out, rows, append=args.append)
    verb = "Appended" if args.append else "Wrote"
    print(f"{verb} {len(rows)} package-line rows -> {out.resolve()}")
    if args.print_counts:
        from collections import defaultdict

        by_t: dict[str, list] = defaultdict(list)
        for r in rows:
            by_t[str(r.get("transfer_object_id") or "")].append(r)
        for tid, rs in sorted(by_t.items(), key=lambda x: (x[1][0].get("received_at") or ""), reverse=True):
            u = sum(int(x.get("original_qty") or 0) for x in rs)
            print(f"  {tid}  lines={len(rs)}  units={u}", file=sys.stderr)


if __name__ == "__main__":
    main()
