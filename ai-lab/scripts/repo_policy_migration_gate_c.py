#!/usr/bin/env python3
"""
Approval tool: Gate C policy/schema migration full rebuild staging -> promote.

Executed via `brain/execution.run()` with args from the hub approval submission.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add ai-lab root so we can import brain modules
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from brain.worker_clients import worker_assistant_index_repo, worker_assistant_promote_repo_index, worker_assistant_retrieve  # noqa: E402


def _extract_staging_version(worker_index_result: dict) -> str | None:
    data = worker_index_result.get("data") or {}
    meta = data.get("meta") or {}
    return meta.get("staging_version") or data.get("staging_version")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo_id", required=True)
    p.add_argument("--gate", required=False, default="C")
    p.add_argument("--reason", required=False, default="")
    p.add_argument("--expected_policy_hash", required=False, default="")
    p.add_argument("--reported_policy_hash", required=False, default="")
    p.add_argument("--expected_embedding_model_id", required=False, default="")
    p.add_argument("--reported_embedding_model_id", required=False, default="")
    p.add_argument("--expected_index_schema_version", required=False, default="")
    p.add_argument("--reported_index_schema_version", required=False, default="")
    p.add_argument("--current_active_version", required=False, default="")
    p.add_argument("--worker_name", required=False, default="worker-rig-01")
    p.add_argument("--smoke_query", required=False, default="where is repo watcher started")
    args = p.parse_args()

    idx = worker_assistant_index_repo(
        repo_path=".",
        worker_name=args.worker_name,
        repo_id=args.repo_id,
        target="staging",
        mode="policy_migration",
        force_full=True,
        expected_policy_hash=args.expected_policy_hash or None,
        expected_embedding_model_id=args.expected_embedding_model_id or None,
        expected_index_schema_version=args.expected_index_schema_version or None,
    )

    if idx.get("status") != "ok":
        print(json.dumps({"ok": False, "stage": "index_repo", "error": idx.get("error") or idx}, indent=2))
        return 1

    staging_version = _extract_staging_version(idx) or "unknown"

    sm = worker_assistant_retrieve(query=args.smoke_query, worker_name=args.worker_name)
    if sm.get("status") != "ok":
        print(json.dumps({"ok": False, "stage": "smoke_retrieve", "error": sm.get("error") or sm}, indent=2))
        return 2

    pr = worker_assistant_promote_repo_index(repo_id=args.repo_id, staging_version=staging_version, worker_name=args.worker_name)
    if pr.get("status") != "ok":
        print(json.dumps({"ok": False, "stage": "promote_repo_index", "error": pr.get("error") or pr}, indent=2))
        return 3

    print(
        json.dumps(
            {
                "ok": True,
                "repo_id": args.repo_id,
                "gate": args.gate,
                "staging_version": staging_version,
                "expected_policy_hash": args.expected_policy_hash,
                "reported_policy_hash": args.reported_policy_hash,
                "index_meta": (idx.get("data") or {}).get("meta") or {},
                "smoke": sm.get("data"),
                "promote": pr.get("data"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

