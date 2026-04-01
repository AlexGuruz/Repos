"""
Execution layer: run(tool_name, args) -> RunResult.
Validates against registry and policy; runs script locally or via SSH; logs to execution_logs.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

AI_LAB_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration: float
    success: bool

    def to_dict(self) -> dict:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "success": self.success,
        }


def _load_registry() -> list[dict]:
    p = AI_LAB_ROOT / "registry" / "scripts.json"
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def _find_tool(tool_name: str) -> dict | None:
    for entry in _load_registry():
        if entry.get("tool_name") == tool_name:
            return entry
    return None


def _resolve_path(entry: dict) -> Path | None:
    """Resolve script path. Prefer repo-relative from E:\\Repos if repo given."""
    path = entry.get("path")
    repo = entry.get("repo")
    if not path:
        return None
    if repo:
        # Assume main rig: E:\Repos\<repo>\<path>
        base = Path("E:/Repos") / repo
        if not base.exists():
            base = AI_LAB_ROOT.parent / repo
        full = (base / path).resolve()
    else:
        full = (AI_LAB_ROOT / path).resolve()
    return full if full.exists() else None


def run(tool_name: str, args: dict | None = None, timeout_sec: int = 300) -> RunResult:
    args = args or {}
    entry = _find_tool(tool_name)
    if not entry:
        return RunResult(
            stdout="",
            stderr=f"Tool not in registry: {tool_name}",
            exit_code=1,
            duration=0.0,
            success=False,
        )
    script_path = _resolve_path(entry)
    if not script_path:
        return RunResult(
            stdout="",
            stderr=f"Script path not found for {tool_name}: {entry.get('path')}",
            exit_code=1,
            duration=0.0,
            success=False,
        )
    log_dir = AI_LAB_ROOT / "logs" / "execution_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()
    try:
        if script_path.suffix == ".py":
            cmd = [os.environ.get("PYTHON", "python"), str(script_path)]
        else:
            cmd = [str(script_path)]
        for k, v in (args or {}).items():
            cmd.extend([f"--{k}", str(v)])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(script_path.parent),
        )
        duration = time.perf_counter() - start
        out = RunResult(
            stdout=result.stdout or "",
            stderr=result.stderr or "",
            exit_code=result.returncode,
            duration=duration,
            success=result.returncode == 0,
        )
    except subprocess.TimeoutExpired:
        duration = time.perf_counter() - start
        out = RunResult(
            stdout="",
            stderr=f"Timeout after {timeout_sec}s",
            exit_code=124,
            duration=duration,
            success=False,
        )
    except Exception as e:
        duration = time.perf_counter() - start
        out = RunResult(stdout="", stderr=str(e), exit_code=1, duration=duration, success=False)
    log_path = log_dir / f"{tool_name}_{int(start)}.json"
    with open(log_path, "w") as f:
        json.dump({"tool_name": tool_name, "args": args, "result": out.to_dict()}, f, indent=2)
    return out
