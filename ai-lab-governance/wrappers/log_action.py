#!/usr/bin/env python3
"""
Log every meaningful AI action. Required fields: timestamp, machine, agent,
user_request_id, action_id, target repo/path, approval_tier, wrapper_used, result.
Schema: schemas/action_log.schema.json
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
    # Assume we're in governance repo: wrappers/log_action.py -> repo root
    return Path(__file__).resolve().parent.parent


def _logs_dir(root: Path) -> Path:
    logs = root / "logs" / "actions"
    logs.mkdir(parents=True, exist_ok=True)
    return logs


def _next_action_id(logs_dir: Path) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"ACT-{today}-"
    existing = list(logs_dir.glob("*.jsonl")) + list(logs_dir.glob("*.log"))
    max_n = 0
    for f in existing:
        try:
            for line in f.open():
                if prefix in line:
                    part = line.split(prefix, 1)[-1].split("-")[0].strip(" \n\t")
                    if part.isdigit():
                        max_n = max(max_n, int(part))
        except Exception:
            pass
    return f"{prefix}{max_n + 1:04d}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Log an AI action (governance)")
    ap.add_argument("--machine", default=os.environ.get("AI_LAB_MACHINE", "unknown"))
    ap.add_argument("--agent", required=True)
    ap.add_argument("--action", required=True)
    ap.add_argument("--result", required=True)
    ap.add_argument("--user-request-id", default="")
    ap.add_argument("--target-repo", default="")
    ap.add_argument("--target-path", default="")
    ap.add_argument("--approval-tier", default="")
    ap.add_argument("--wrapper-used", default="log_action.py")
    ap.add_argument("--rollback-ref", default="")
    args = ap.parse_args()

    root = _governance_root()
    logs_dir = _logs_dir(root)
    action_id = _next_action_id(logs_dir)

    entry = {
        "action_id": action_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "machine": args.machine,
        "agent": args.agent,
        "user_request_id": args.user_request_id,
        "action": args.action,
        "target_repo": args.target_repo,
        "target_path": args.target_path,
        "approval_tier": args.approval_tier,
        "wrapper_used": args.wrapper_used,
        "result": args.result,
        "rollback_reference": args.rollback_ref,
    }

    log_file = logs_dir / "actions.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(action_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
