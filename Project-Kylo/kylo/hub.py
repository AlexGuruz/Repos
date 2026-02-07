from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent

from services.common.instance import (
    default_health_path,
    default_watcher_log_path,
    instance_logs_dir,
)
from services.ops.dashboard import write_dashboard_json


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML not installed; required for hub instance registry")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"Invalid YAML root in {path} (expected mapping)")
    return raw


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system().lower().startswith("win"):
        # Windows: use GetExitCodeProcess for a reliable liveness check
        try:
            import ctypes
            from ctypes import wintypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259

            OpenProcess = ctypes.windll.kernel32.OpenProcess
            OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            OpenProcess.restype = wintypes.HANDLE

            GetExitCodeProcess = ctypes.windll.kernel32.GetExitCodeProcess
            GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            GetExitCodeProcess.restype = wintypes.BOOL

            CloseHandle = ctypes.windll.kernel32.CloseHandle
            CloseHandle.argtypes = [wintypes.HANDLE]
            CloseHandle.restype = wintypes.BOOL

            h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            code = wintypes.DWORD()
            ok = GetExitCodeProcess(h, ctypes.byref(code))
            CloseHandle(h)
            if not ok:
                return False
            return int(code.value) == STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def _terminate_pid(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system().lower().startswith("win"):
        try:
            # /T: kill child processes; /F: force
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False


@dataclass
class InstanceSpec:
    id: str
    company_key: str
    years: str
    enabled: bool = True


def load_instance_registry(path: Path) -> List[InstanceSpec]:
    data = _load_yaml(path)
    items = data.get("instances") or []
    if not isinstance(items, list):
        raise RuntimeError(f"Invalid registry format in {path}: 'instances' must be a list")
    specs: List[InstanceSpec] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        iid = str(it.get("id") or "").strip()
        if not iid:
            continue
        specs.append(
            InstanceSpec(
                id=iid,
                company_key=str(it.get("company_key") or "").strip().upper() or iid.split("_", 1)[0].upper(),
                years=str(it.get("years") or "").strip() or "",
                enabled=bool(it.get("enabled", True)),
            )
        )
    return specs


def hub_paths() -> tuple[Path, Path]:
    hub_dir = Path(".kylo") / "hub"
    status_path = hub_dir / "status.json"
    log_path = hub_dir / "hub.log"
    return status_path, log_path


def hub_log(msg: str) -> None:
    status_path, log_path = hub_paths()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{_utc_now_iso()} {msg}\n"
    try:
        log_path.open("a", encoding="utf-8").write(line)
    except Exception:
        pass


def write_status(instances: Dict[str, Dict[str, Any]]) -> None:
    status_path, _ = hub_paths()
    payload = {"updated_at": _utc_now_iso(), "instances": instances}
    _atomic_write_json(status_path, payload)


def read_status() -> Dict[str, Any]:
    status_path, _ = hub_paths()
    if not status_path.exists():
        return {"updated_at": None, "instances": {}}
    try:
        return json.loads(status_path.read_text(encoding="utf-8")) or {"instances": {}}
    except Exception:
        return {"updated_at": None, "instances": {}}


def build_watcher_cmd(spec: InstanceSpec) -> List[str]:
    # Use an importable module so installed-mode doesn't depend on `bin/`.
    cmd = [sys.executable, "-u", "-m", "kylo.watcher_runtime"]
    if spec.years:
        cmd += ["--years", spec.years]
    cmd += ["--instance-id", spec.id]
    return cmd


def spawn_watcher(spec: InstanceSpec, *, extra_env: Optional[Dict[str, str]] = None) -> subprocess.Popen:
    cmd = build_watcher_cmd(spec)

    # Logs go per-instance
    log_path = default_watcher_log_path(spec.id)
    instance_logs_dir(spec.id).mkdir(parents=True, exist_ok=True)
    out = log_path.open("a", encoding="utf-8")

    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["KYLO_INSTANCE_ID"] = spec.id
    if spec.years:
        env["KYLO_ACTIVE_YEARS"] = spec.years
    env.setdefault("KYLO_CONFIG_PATH", os.path.join("config", "global.yaml"))
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})

    creationflags = 0
    if platform.system().lower().startswith("win"):
        try:
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        except Exception:
            creationflags = 0

    # Start watcher as child process; stdout/stderr captured to log file
    proc = subprocess.Popen(
        cmd,
        cwd=os.getcwd(),
        env=env,
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
        text=True,
    )
    # Avoid leaking file handles in the hub process (child keeps its own handle).
    try:
        out.close()
    except Exception:
        pass
    return proc


def compute_backoff_seconds(restarts: int, *, base: int = 5, cap: int = 300) -> int:
    # 5,10,20,40,... up to cap
    secs = base * (2 ** max(0, restarts))
    return min(cap, secs)


def run_supervisor(
    specs: List[InstanceSpec],
    *,
    poll_secs: int = 2,
    max_restarts: int = 10,
    restart_window_secs: int = 1800,
) -> int:
    # Track runtime state in-memory
    procs: Dict[str, subprocess.Popen] = {}
    state: Dict[str, Dict[str, Any]] = {}
    restarts: Dict[str, List[float]] = {s.id: [] for s in specs}
    paused: set[str] = set()
    next_ops_rollup_at = 0.0
    restart_at: Dict[str, float] = {}

    def _register(spec: InstanceSpec, *, proc: Optional[subprocess.Popen], status: str) -> None:
        pid = proc.pid if proc else state.get(spec.id, {}).get("pid")
        state[spec.id] = {
            "pid": pid,
            "enabled": spec.enabled,
            "state": status,
            "started_at": state.get(spec.id, {}).get("started_at") or _utc_now_iso(),
            "restarts": len(restarts.get(spec.id, [])),
            "last_exit": state.get(spec.id, {}).get("last_exit"),
            "health_path": str(default_health_path(spec.id)),
            "log_path": str(default_watcher_log_path(spec.id)),
            "years": spec.years,
        }
        write_status(state)

    hub_log(f"[hub] starting supervisor for {len(specs)} instance(s)")

    for spec in specs:
        if not spec.enabled:
            _register(spec, proc=None, status="disabled")
            continue
        try:
            proc = spawn_watcher(spec)
            procs[spec.id] = proc
            state[spec.id] = {
                "pid": proc.pid,
                "enabled": spec.enabled,
                "state": "running",
                "started_at": _utc_now_iso(),
                "restarts": 0,
                "last_exit": None,
                "health_path": str(default_health_path(spec.id)),
                "log_path": str(default_watcher_log_path(spec.id)),
                "years": spec.years,
            }
            hub_log(f"[hub] started {spec.id} pid={proc.pid} years='{spec.years}'")
        except Exception as e:
            state[spec.id] = {
                "pid": None,
                "enabled": spec.enabled,
                "state": "error",
                "started_at": None,
                "restarts": 0,
                "last_exit": None,
                "last_error": str(e),
                "health_path": str(default_health_path(spec.id)),
                "log_path": str(default_watcher_log_path(spec.id)),
                "years": spec.years,
            }
            hub_log(f"[hub] failed to start {spec.id}: {e}")
    write_status(state)

    try:
        while True:
            now = time.time()
            if now >= next_ops_rollup_at:
                try:
                    write_dashboard_json()
                except Exception:
                    pass
                next_ops_rollup_at = now + 10.0

            # Handle scheduled restarts without blocking the whole hub.
            for spec in specs:
                if not spec.enabled or spec.id in paused:
                    continue
                at = restart_at.get(spec.id)
                if at is None or now < at:
                    continue
                restart_at.pop(spec.id, None)
                try:
                    proc2 = spawn_watcher(spec)
                    procs[spec.id] = proc2
                    state.setdefault(spec.id, {})
                    state[spec.id]["pid"] = proc2.pid
                    state[spec.id]["state"] = "running"
                    state[spec.id]["started_at"] = _utc_now_iso()
                    write_status(state)
                    hub_log(f"[hub] restarted {spec.id} pid={proc2.pid}")
                except Exception as e:
                    state.setdefault(spec.id, {})
                    state[spec.id]["state"] = "error"
                    state[spec.id]["last_error"] = str(e)
                    write_status(state)
                    hub_log(f"[hub] failed to restart {spec.id}: {e}")

            for spec in specs:
                if not spec.enabled:
                    continue
                if spec.id in paused:
                    continue
                if spec.id in restart_at:
                    continue
                proc = procs.get(spec.id)
                if proc is None:
                    continue
                code = proc.poll()
                if code is None:
                    # still running
                    continue

                # exited
                state.setdefault(spec.id, {})["last_exit"] = int(code)
                hub_log(f"[hub] {spec.id} exited code={code}")

                # restart policy
                history = restarts.setdefault(spec.id, [])
                history.append(now)
                # prune outside window
                history[:] = [t for t in history if (now - t) <= restart_window_secs]
                if len(history) > max_restarts:
                    paused.add(spec.id)
                    state[spec.id]["state"] = "paused"
                    state[spec.id]["restarts"] = len(history)
                    hub_log(f"[hub] pausing {spec.id} (too many restarts in window)")
                    write_status(state)
                    continue

                delay = compute_backoff_seconds(len(history) - 1)
                state[spec.id]["state"] = "scheduled_restart"
                state[spec.id]["restarts"] = len(history)
                write_status(state)
                hub_log(f"[hub] scheduling restart {spec.id} after {delay}s (restarts={len(history)})")
                restart_at[spec.id] = now + float(delay)

            time.sleep(max(1, poll_secs))
    except KeyboardInterrupt:
        hub_log("[hub] received Ctrl+C, stopping children")
    finally:
        for spec in specs:
            proc = procs.get(spec.id)
            if proc and proc.poll() is None:
                try:
                    _terminate_pid(proc.pid)
                except Exception:
                    pass
        hub_log("[hub] stopped")
    return 0


def cmd_status() -> int:
    data = read_status()
    inst = data.get("instances") or {}
    print(f"updated_at: {data.get('updated_at')}")
    for iid, info in inst.items():
        pid = info.get("pid")
        alive = _pid_alive(int(pid)) if pid else False
        state = info.get("state")
        years = info.get("years")
        # Enrich display with heartbeat snapshot (best-effort)
        hb_path = Path(str(info.get("health_path") or ""))
        last_tick = ""
        last_post = ""
        last_err = ""
        try:
            if hb_path and hb_path.exists():
                hb = json.loads(hb_path.read_text(encoding="utf-8")) or {}
                last_tick = str(hb.get("last_tick_at") or "")
                lpo = hb.get("last_post_ok")
                last_post = "" if lpo is None else ("OK" if bool(lpo) else "FAIL")
                last_err = str(hb.get("last_error") or "")
        except Exception:
            pass
        extra = f" last_tick={last_tick}" if last_tick else ""
        extra += f" last_post={last_post}" if last_post else ""
        extra += f" last_error={last_err}" if last_err else ""
        print(f"- {iid}: state={state} pid={pid} alive={alive} years='{years}'{extra}")
    return 0


def cmd_stop(instance: Optional[str] = None) -> int:
    data = read_status()
    inst = data.get("instances") or {}
    targets = [instance] if instance else list(inst.keys())
    for iid in targets:
        info = inst.get(iid) or {}
        pid = info.get("pid")
        if not pid:
            continue
        try:
            _terminate_pid(int(pid))
            hub_log(f"[hub] stop requested for {iid} pid={pid}")
            info["state"] = "stopped"
            info["pid"] = None
            info["last_exit"] = info.get("last_exit")
            inst[iid] = info
        except Exception:
            continue
    write_status(instances=inst)
    return 0


def select_specs(specs: List[InstanceSpec], *, all_enabled: bool, instance: Optional[str]) -> List[InstanceSpec]:
    if instance:
        chosen = [s for s in specs if s.id == instance]
        if not chosen:
            raise RuntimeError(f"Unknown instance id: {instance}")
        # force-enable if explicitly selected
        chosen[0].enabled = True
        return chosen
    if all_enabled:
        return [s for s in specs if s.enabled]
    raise RuntimeError("Must specify --all or --instance")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kylo watcher supervisor hub")
    p.add_argument(
        "--registry",
        default=os.path.join("config", "instances", "index.yaml"),
        help="Path to instance registry YAML (default: config/instances/index.yaml)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="Start hub supervisor (foreground)")
    sp.add_argument("--all", action="store_true", help="Start all enabled instances")
    sp.add_argument("--instance", default=None, help="Start only one instance id")
    sp.add_argument("--poll-secs", type=int, default=2, help="Poll interval for child health checks")
    sp.add_argument("--max-restarts", type=int, default=10, help="Max restarts allowed in window before pausing")
    sp.add_argument("--restart-window-secs", type=int, default=1800, help="Restart window duration in seconds")

    sp2 = sub.add_parser("stop", help="Stop instances using status registry")
    sp2.add_argument("--all", action="store_true", help="Stop all instances in status registry")
    sp2.add_argument("--instance", default=None, help="Stop one instance id")

    sub.add_parser("status", help="Show status registry + pid liveness")

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    registry_path = Path(args.registry)
    specs = load_instance_registry(registry_path)

    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "stop":
        if not args.all and not args.instance:
            raise SystemExit("stop requires --all or --instance")
        return cmd_stop(instance=args.instance if not args.all else None)
    if args.cmd == "start":
        chosen = select_specs(specs, all_enabled=bool(args.all), instance=args.instance)
        return run_supervisor(
            chosen,
            poll_secs=int(args.poll_secs),
            max_restarts=int(args.max_restarts),
            restart_window_secs=int(args.restart_window_secs),
        )
    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

