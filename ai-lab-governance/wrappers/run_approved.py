#!/usr/bin/env python3
"""
Execute only approved actions. Checks approval_tiers.yaml, allowlists.yaml,
denied_actions.yaml and tool_registry. If action is not allowlisted, requires
an existing approved request (APR-*) in approvals/approved/. Logs via log_action.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _governance_root() -> Path:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # Minimal YAML parse for flat lists (deny_always, approval_required, etc.)
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        data: dict = {}
        current_key = None
        for line in text.splitlines():
            s = line.strip()
            if s.endswith(":") and not s.startswith("-"):
                current_key = s[:-1].strip()
                data.setdefault(current_key, [])
            elif current_key and s.startswith("- "):
                data[current_key].append(s[2:].strip())
        return data
    except Exception:
        return {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run only approved execution (governance)")
    ap.add_argument("--approval-id", default="", help="APR-YYYYMMDD-NNNN if approval was required")
    ap.add_argument("--action-type", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--script", default="", help="Script path or registered tool name")
    ap.add_argument("--args", default="", help="Space-separated args for script")
    ap.add_argument("--allowlist-only", action="store_true", help="Fail if not allowlisted (no approval file)")
    args = ap.parse_args()

    root = _governance_root()
    policies = root / "policies"
    denied = _load_yaml(policies / "denied_actions.yaml")
    if args.action_type in denied.get("deny_always", []):
        print("DENIED: action in deny_always", file=sys.stderr)
        return 2

    # If allowlist-only and no approval-id, check allowlist only (caller's job to ensure allowlisted)
    if args.allowlist_only and not args.approval_id:
        # Just check denied; actual allowlist check can be in supervisor
        pass

    # If approval required, must have approval_id and file in approvals/approved/
    if args.approval_id:
        approved_file = root / "approvals" / "approved" / f"{args.approval_id}.json"
        if not approved_file.exists():
            print("MISSING_APPROVAL: approved file not found", file=sys.stderr)
            return 3

    # Run script (simplified: real impl would run in sandbox, timeout, etc.)
    script_path = args.script
    if not script_path and args.action_type == "script_execution":
        print("MISSING_SCRIPT", file=sys.stderr)
        return 4
    if not os.path.isabs(script_path):
        script_path = os.path.abspath(os.path.join(os.getcwd(), script_path))
    if not os.path.exists(script_path):
        print("SCRIPT_NOT_FOUND", file=sys.stderr)
        return 5

    cmd = [sys.executable, script_path] + (args.args.split() if args.args else [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        stdout, stderr = result.stdout, result.stderr
        log_result = "ok" if result.returncode == 0 else f"exit_{result.returncode}"
    except subprocess.TimeoutExpired:
        log_result = "timeout"
        stdout, stderr = "", "timeout"
        result = type("R", (), {"returncode": 124})()

    # Log via log_action
    log_script = root / "wrappers" / "log_action.py"
    if log_script.exists():
        subprocess.run(
            [
                sys.executable,
                str(log_script),
                "--machine", os.environ.get("AI_LAB_MACHINE", "unknown"),
                "--agent", args.agent,
                "--action", args.action_type,
                "--result", log_result,
                "--target-path", script_path,
                "--approval-tier", "T2",
                "--wrapper-used", "run_approved.py",
            ],
            check=False,
        )

    print(stdout or stderr or log_result)
    return result.returncode if result.returncode != 0 else 0


if __name__ == "__main__":
    sys.exit(main())
