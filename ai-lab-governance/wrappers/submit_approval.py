#!/usr/bin/env python3
"""
Submit an approval request for a state-changing action. Writes to approvals/proposals/
with request_id APR-YYYYMMDD-NNNN. Supervisor or human approves/denies later.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _governance_root() -> Path:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def _next_approval_id(approvals_dir: Path) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"APR-{today}-"
    proposals = approvals_dir / "proposals"
    proposals.mkdir(parents=True, exist_ok=True)
    max_n = 0
    for f in proposals.iterdir() if proposals.exists() else []:
        if f.suffix == ".json" and f.stem.startswith(prefix):
            try:
                n = int(f.stem.replace(prefix, ""))
                max_n = max(max_n, n)
            except ValueError:
                pass
    return f"{prefix}{max_n + 1:04d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Submit approval request (governance)")
    ap.add_argument("--action-type", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--reason", default="")
    ap.add_argument("--machine", default=os.environ.get("AI_LAB_MACHINE", "unknown"))
    ap.add_argument("--diff-preview", default="")
    ap.add_argument("--risk-level", default="medium", choices=["low", "medium", "high", "critical"])
    ap.add_argument("--scope-repo", default="")
    ap.add_argument("--payload", default="{}", help="JSON string for extra fields")
    args = ap.parse_args()

    root = _governance_root()
    approvals_dir = root / "approvals"
    approvals_dir.mkdir(parents=True, exist_ok=True)
    proposals_dir = approvals_dir / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)

    request_id = _next_approval_id(approvals_dir)
    payload = json.loads(args.payload) if args.payload else {}

    doc = {
        "request_id": request_id,
        "action_type": args.action_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "machine": args.machine,
        "target": args.target,
        "reason": args.reason,
        "diff_preview": args.diff_preview,
        "risk_level": args.risk_level,
        "scope_repo": args.scope_repo,
        "status": "pending",
        **payload,
    }

    out_file = proposals_dir / f"{request_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)

    print(request_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
