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
from typing import Any

from brain.approval_enforcement import evaluate_action

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


def _cli_args_from_dict(args: dict[str, Any]) -> list[str]:
    """Build script argv: underscores → dashes; bool True → flag only."""
    argv: list[str] = []
    for key, value in (args or {}).items():
        flag = f"--{str(key).replace('_', '-')}"
        if value is True:
            argv.append(flag)
        elif value is False or value is None:
            continue
        else:
            argv.extend([flag, str(value)])
    return argv


def _resolve_path(entry: dict) -> Path | None:
    """Resolve script path. Prefer repo-relative from E:\\Repos if repo given."""
    path = entry.get("path")
    repo = entry.get("repo")
    if not path:
        return None
    candidates: list[Path] = []
    if repo:
        # Assume main rig: E:\Repos\<repo>\<path>
        base = Path("E:/Repos") / repo
        if not base.exists():
            base = AI_LAB_ROOT.parent / repo
        candidates.append((base / path))
        # Legacy registry rows accidentally double-prefix the repo folder.
        # e.g. repo=Growflow path=Growflow/scripts/... → E:/Repos/Growflow/scripts/...
        if path.replace("\\", "/").startswith(f"{repo}/"):
            candidates.append(base / path[len(repo) + 1 :])
        candidates.append(AI_LAB_ROOT.parent / path)
    else:
        candidates.append(AI_LAB_ROOT / path)
    for full in candidates:
        try:
            resolved = full.resolve()
        except OSError:
            continue
        if resolved.exists():
            return resolved
    return None


def run(
    tool_name: str,
    args: dict | None = None,
    timeout_sec: int = 300,
    *,
    approval_context: dict[str, Any] | None = None,
) -> RunResult:
    args = args or {}
    approval_context = approval_context or {}
    approved = bool(approval_context.get("approved"))
    decision = evaluate_action(
        action="run_script",
        tool_name=tool_name,
        approved=approved,
        fail_closed_on_missing_metadata=True,
    )
    if not decision.allowed:
        return RunResult(
            stdout="",
            stderr=f"Execution blocked by approval policy: {decision.reason}",
            exit_code=3,
            duration=0.0,
            success=False,
        )
    entry = _find_tool(tool_name)
    if not entry:
        return RunResult(
            stdout="",
            stderr=f"Tool not in registry: {tool_name}",
            exit_code=1,
            duration=0.0,
            success=False,
        )
    if entry.get("executable") is False or str(entry.get("status") or "").lower() == "deprecated":
        return RunResult(
            stdout="",
            stderr=(
                f"Tool {tool_name} is not executable "
                f"(status={entry.get('status')!r}). Use Operator Desk read tools instead."
            ),
            exit_code=3,
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
        cmd.extend(_cli_args_from_dict(args))
        cwd = str(AI_LAB_ROOT) if entry.get("repo") == "ai-lab" else str(script_path.parent)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=cwd,
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


def run_bank_vendor_cleaner(
    params: dict[str, Any] | None = None,
    *,
    approval_context: dict[str, Any] | None = None,
    timeout_sec: int = 300,
) -> RunResult:
    """
    Run bank_vendor_cleaner_pipeline (scripts/sheet_label_pipeline.py).
    Defaults to dry-run preview unless params['dry_run'] is False and approval granted.
    """
    from brain.bank_vendor_cleaner.loader import load_manifest

    params = dict(params or {})
    manifest = load_manifest()
    scope = manifest.get("single_sheet_scope") or {}
    spreadsheet_id = (
        params.get("spreadsheet_id")
        or os.environ.get("SPREADSHEET_ID")
        or scope.get("spreadsheet_id")
        or ""
    )
    dry_run = params.get("dry_run", True)
    if isinstance(dry_run, str):
        dry_run = dry_run.strip().lower() in {"1", "true", "yes", "on"}

    cli_args: dict[str, Any] = {}
    if spreadsheet_id:
        cli_args["spreadsheet_id"] = spreadsheet_id
    if params.get("source_sheet_name"):
        cli_args["source_sheet_name"] = params["source_sheet_name"]
    if params.get("dest_sheet_name"):
        cli_args["dest_sheet_name"] = params["dest_sheet_name"]

    if dry_run:
        cli_args["dry_run"] = True
    else:
        cli_args["no_dry_run"] = True
        if approval_context and approval_context.get("approved"):
            cli_args["approved"] = True

    return run(
        "bank_vendor_cleaner_pipeline",
        cli_args,
        timeout_sec=timeout_sec,
        approval_context=approval_context,
    )


def run_bank_vendor_lookup_worker(
    params: dict[str, Any] | None = None,
    *,
    approval_context: dict[str, Any] | None = None,
    timeout_sec: int = 120,
) -> RunResult:
    """Run bank_vendor_lookup_worker (scripts/vendor_lookup_worker.py). No sheet writes."""
    params = dict(params or {})
    cli_args: dict[str, Any] = {}
    if params.get("raw_input"):
        cli_args["raw_input"] = params["raw_input"]
    if params.get("city_hint"):
        cli_args["city_hint"] = params["city_hint"]
    if params.get("state_hint"):
        cli_args["state_hint"] = params["state_hint"]
    dry_run = params.get("dry_run", True)
    if isinstance(dry_run, str):
        dry_run = dry_run.strip().lower() in {"1", "true", "yes", "on"}
    if dry_run:
        cli_args["dry_run"] = True
    else:
        cli_args["no_dry_run"] = True
    return run(
        "bank_vendor_lookup_worker",
        cli_args,
        timeout_sec=timeout_sec,
        approval_context=approval_context,
    )
