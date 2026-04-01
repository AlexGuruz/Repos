"""
SSH worker adapter: run commands on a worker rig over SSH, return stdout/stderr.
Used for worker-backed flows (e.g. repo_cartographer). Main persists results to summaries/.
"""
from __future__ import annotations

import os
import subprocess
from typing import NamedTuple


class SSHResult(NamedTuple):
    stdout: str
    stderr: str
    returncode: int


def get_worker_ssh_config() -> dict | None:
    """
    Return worker SSH config if configured: {"host": str, "user": str, "ai_lab_path": str}.
    None if WORKER_SSH_HOST is not set (use local execution).
    """
    host = (os.environ.get("WORKER_SSH_HOST") or "").strip()
    if not host:
        return None
    user = (os.environ.get("WORKER_SSH_USER") or "").strip() or None
    ai_lab_path = (os.environ.get("WORKER_AI_LAB_PATH") or "").strip() or "."
    return {"host": host, "user": user, "ai_lab_path": ai_lab_path}


def run_ssh_command(
    host: str,
    command: str,
    user: str | None = None,
    timeout_sec: int = 120,
) -> SSHResult:
    """
    Run command on host via SSH. Uses 'ssh host' or 'ssh user@host' if user given.
    Returns (stdout, stderr, returncode).
    """
    target = f"{user}@{host}" if user else host
    full_cmd = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", target, command]
    try:
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        return SSHResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            returncode=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return SSHResult(stdout="", stderr=f"SSH timeout after {timeout_sec}s", returncode=124)
    except FileNotFoundError:
        return SSHResult(stdout="", stderr="ssh not found", returncode=127)
    except Exception as e:
        return SSHResult(stdout="", stderr=str(e), returncode=1)
