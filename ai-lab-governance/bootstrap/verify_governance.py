#!/usr/bin/env python3
"""
Verify governance repo is present and aligned: required files, Cursor rules,
wrappers, registry, logs/approvals paths. Exit 0 = pass, non-zero = fail.
Run on both main and worker rigs to detect drift.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _governance_root() -> Path:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if root:
        return Path(root)
    # Assume run from bootstrap/ or repo root
    script = Path(__file__).resolve()
    if script.parent.name == "bootstrap":
        return script.parent.parent
    return script.parent


REQUIRED_FILES = [
    "AGENTS.md",
    "GLOBAL_POLICY.md",
    "CATALOG_SSOT_IMPLEMENTATION_PLAN.md",
    "configs/governance_version.yaml",
    "cursor/cursor_rules.md",
    "cursor/prompts/orchestrator_system.txt",
    "cursor/prompts/worker_system.txt",
    "cursor/prompts/business_tooling_system.txt",
    "policies/approval_tiers.yaml",
    "policies/allowlists.yaml",
    "policies/denied_actions.yaml",
    "policies/memory_rules.yaml",
    "policies/repo_classes.yaml",
    "policies/execution_rules.yaml",
    "registry/tool_registry.json",
    "registry/repo_registry.json",
    "registry/agent_registry.json",
    "registry/components.yaml",
    "registry/environments.yaml",
    "registry/README_catalog.md",
    "schemas/approval_request.schema.json",
    "schemas/action_log.schema.json",
    "schemas/job.schema.json",
    "schemas/memory_event.schema.json",
    "schemas/component.schema.json",
    "schemas/environment.schema.json",
    "wrappers/run_approved.py",
    "wrappers/submit_approval.py",
    "wrappers/log_action.py",
    "wrappers/read_registry.py",
    "wrappers/safe_exec.py",
]

REQUIRED_DIRS = [
    "logs/actions",
    "approvals/proposals",
    "approvals/approved",
    "approvals/denied",
]


def main() -> int:
    root = _governance_root()
    if not root.is_dir():
        print("FAIL: governance root not a directory:", root, file=sys.stderr)
        return 1

    failed = []

    for rel in REQUIRED_FILES:
        p = root / rel
        if not p.exists():
            failed.append(f"missing file: {rel}")
        elif p.is_dir():
            failed.append(f"expected file, is dir: {rel}")

    for rel in REQUIRED_DIRS:
        p = root / rel
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                failed.append(f"missing dir (create failed): {rel} ({e})")
        elif not p.is_dir():
            failed.append(f"expected dir, not dir: {rel}")

    # Wrappers must be executable/readable
    for w in ["log_action.py", "read_registry.py", "run_approved.py", "submit_approval.py", "safe_exec.py"]:
        wp = root / "wrappers" / w
        if not wp.exists() or not os.access(wp, os.R_OK):
            failed.append(f"wrapper not readable: wrappers/{w}")

    if failed:
        for f in failed:
            print("FAIL:", f, file=sys.stderr)
        return 2

    # Optional: machine-checkable system catalog (requires PyYAML + jsonschema)
    if os.environ.get("AI_LAB_VERIFY_CATALOG", "").strip() in ("1", "true", "yes"):
        catalog_script = root / "scripts" / "verify_catalog.py"
        if catalog_script.is_file():
            r = subprocess.run(
                [sys.executable, str(catalog_script)],
                cwd=str(root),
                env=os.environ.copy(),
            )
            if r.returncode != 0:
                return r.returncode

    # Optional: hash policy files and compare to expected (for strict drift)
    # if os.environ.get("AI_LAB_VERIFY_HASHES"):
    #     ...

    print("OK: governance verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
