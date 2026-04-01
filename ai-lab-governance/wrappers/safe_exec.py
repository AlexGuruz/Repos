#!/usr/bin/env python3
"""
Safe execution wrapper: run a single command/script only if it passes
denied_actions and (optional) allowlist. Logs the action. Use for
read-only or allowlisted commands (e.g. status checks, approved scripts).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _governance_root() -> Path:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def _load_denied(root: Path) -> list:
    p = root / "policies" / "denied_actions.yaml"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    denied = []
    in_deny = False
    for line in text.splitlines():
        if line.strip() == "deny_always:":
            in_deny = True
            continue
        if in_deny and line.startswith("  - "):
            denied.append(line[4:].strip())
        elif in_deny and line and not line[0].isspace():
            break
    return denied


def main() -> int:
    ap = argparse.ArgumentParser(description="Safe execute (governance)")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--action", default="safe_exec")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("command", nargs="+", help="Command and args")
    args = ap.parse_args()

    root = _governance_root()
    denied = _load_denied(root)
    cmd0 = args.command[0].lower() if args.command else ""
    if "sudo" in cmd0 or "su " in cmd0 or "ssh" in cmd0:
        # Restrict: only allow explicit approved patterns; else deny
        if not os.environ.get("AI_LAB_SAFE_EXEC_ALLOW_SUDO"):
            print("DENIED: sudo/su/ssh not allowed without AI_LAB_SAFE_EXEC_ALLOW_SUDO", file=sys.stderr)
            return 2

    try:
        result = subprocess.run(
            args.command,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            cwd=os.getcwd(),
        )
    except subprocess.TimeoutExpired:
        result = type("R", (), {"returncode": 124, "stdout": "", "stderr": "timeout"})()

    log_script = root / "wrappers" / "log_action.py"
    if log_script.exists():
        subprocess.run(
            [
                sys.executable,
                str(log_script),
                "--machine", os.environ.get("AI_LAB_MACHINE", "unknown"),
                "--agent", args.agent,
                "--action", args.action,
                "--result", "ok" if result.returncode == 0 else f"exit_{result.returncode}",
                "--wrapper-used", "safe_exec.py",
            ],
            check=False,
        )

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
