"""Sandbox live-mirror daemon — keep KYLO_2026_SANDBOX intake current with live.

Polls the LIVE 2026 TRANSACTIONS + BANK tabs every ``interval_seconds`` (default
120). When the fingerprint changes, copies full rows (including Processed /
Approved / NOTES / log columns) into the matching sandbox tabs, then rebuilds
BALANCE so Cash/Bank EOD track day-to-day.

One-way only. Never writes the live workbook. Isolated from KYLO_2025 / KYLO_2026
watchers (uses KYLO_INSTANCE_ID=KYLO_2026_SANDBOX state/logs only).

Usage:
  PYTHONPATH=. python scripts/sandbox_live_mirror_daemon.py
  PYTHONPATH=. python scripts/sandbox_live_mirror_daemon.py --once
  PYTHONPATH=. python scripts/sandbox_live_mirror_daemon.py --interval 120 --force
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

os.environ.setdefault("KYLO_INSTANCE_ID", "KYLO_2026_SANDBOX")

from services.sandbox.intake_mirror import (  # noqa: E402
    DEFAULT_LIVE_SID,
    DEFAULT_SA_JSON,
    DEFAULT_SANDBOX_SID,
    load_last_digest,
    sync_intake_live_to_sandbox,
    write_heartbeat,
)

INSTANCE_DIR = REPO / ".kylo" / "instances" / "KYLO_2026_SANDBOX"
LOG_PATH = INSTANCE_DIR / "logs" / "sandbox_mirror.log"
HEARTBEAT_PATH = INSTANCE_DIR / "health" / "sandbox_mirror.json"
DIGEST_PATH = INSTANCE_DIR / "state" / "sandbox_mirror_digest.json"
PID_PATH = INSTANCE_DIR / "state" / "sandbox_mirror.pid"
REBUILD_SCRIPT = REPO / "tools" / "debug" / "_rebuild_balance_from_ledgers.py"


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] sandbox-mirror: {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _acquire_pid_lock() -> bool:
    """Return False if another mirror daemon is already running."""
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    if PID_PATH.exists():
        try:
            old = int((PID_PATH.read_text(encoding="utf-8") or "0").strip() or "0")
        except Exception:
            old = 0
        if old and old != os.getpid() and _pid_alive(old):
            _log(f"another mirror already running (pid={old}); exiting")
            return False
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    return True


def _release_pid_lock() -> None:
    try:
        if PID_PATH.exists() and PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def _cfg_mirror() -> dict:
    """Read sandbox_mirror block from KYLO_2026_SANDBOX.yaml (best-effort)."""
    out = {
        "interval_seconds": 120,
        "rebuild_balance_on_change": True,
        "live_sid": DEFAULT_LIVE_SID,
        "sandbox_sid": DEFAULT_SANDBOX_SID,
        "service_account_json": DEFAULT_SA_JSON,
    }
    try:
        os.environ["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"
        from services.common.config_loader import load_config

        cfg = load_config()
        interval = cfg.get("sandbox_mirror.interval_seconds")
        if interval is not None:
            out["interval_seconds"] = int(interval)
        rebuild = cfg.get("sandbox_mirror.rebuild_balance_on_change")
        if rebuild is not None:
            out["rebuild_balance_on_change"] = bool(rebuild)
        live = cfg.get("sandbox_mirror.live_sid")
        if live:
            out["live_sid"] = str(live).strip()
        sandbox = cfg.get("sandbox_mirror.sandbox_sid")
        if sandbox:
            out["sandbox_sid"] = str(sandbox).strip()
        else:
            # Prefer year workbook URL from instance config when present.
            url = cfg.get("year_workbooks.2026.intake_workbook_url") or ""
            if "spreadsheets/d/" in str(url):
                out["sandbox_sid"] = str(url).split("/d/")[1].split("/")[0]
        sa = cfg.get("sandbox_mirror.service_account_json") or cfg.get(
            "google.service_account_json_path"
        )
        if sa:
            out["service_account_json"] = str(sa).strip()
        enabled = cfg.get("sandbox_mirror.enabled")
        out["enabled"] = True if enabled is None else bool(enabled)
    except Exception as exc:
        _log(f"config load soft-fail ({exc}); using defaults")
        out["enabled"] = True
    return out


def _rebuild_balance() -> bool:
    if not REBUILD_SCRIPT.exists():
        _log(f"rebuild script missing: {REBUILD_SCRIPT}")
        return False
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO)
    env["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"
    _log("rebuilding BALANCE from ledgers ...")
    try:
        proc = subprocess.run(
            [sys.executable, str(REBUILD_SCRIPT)],
            cwd=str(REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "")[-800:]
            _log(f"BALANCE rebuild FAILED rc={proc.returncode}: {tail}")
            return False
        # Surface the D0 line if present.
        for line in (proc.stdout or "").splitlines():
            if "boundary D0" in line or "DONE rebuild" in line:
                _log(line.strip())
        return True
    except subprocess.TimeoutExpired:
        _log("BALANCE rebuild TIMED OUT (300s)")
        return False
    except Exception as exc:
        _log(f"BALANCE rebuild error: {exc}")
        return False


def run_tick(
    *,
    force: bool,
    rebuild_on_change: bool,
    sa_json: str,
    live_sid: str,
    sandbox_sid: str,
) -> dict:
    previous = load_last_digest(DIGEST_PATH)
    result = sync_intake_live_to_sandbox(
        sa_json=sa_json,
        live_sid=live_sid,
        sandbox_sid=sandbox_sid,
        force=force,
        previous_digest=previous,
    )
    rebuilt = False
    ok = result.error is None
    if result.error:
        _log(f"sync ERROR: {result.error}")
    elif not result.changed:
        rows = result.fingerprint.tab_rows
        _log(
            f"unchanged digest={result.fingerprint.digest} "
            f"TX={rows.get('TRANSACTIONS', 0)} BANK={rows.get('BANK', 0)} "
            f"({result.elapsed_seconds}s)"
        )
    else:
        rows = result.rows_written
        _log(
            f"SYNCED digest={result.fingerprint.digest} "
            f"TX_rows={rows.get('TRANSACTIONS', 0)} BANK_rows={rows.get('BANK', 0)} "
            f"(incl. NOTES/log cols) in {result.elapsed_seconds}s"
        )
        DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIGEST_PATH.write_text(
            __import__("json").dumps(
                {
                    "digest": result.fingerprint.digest,
                    "tab_rows": result.fingerprint.tab_rows,
                    "tab_hashes": result.fingerprint.tab_hashes,
                    "synced_at": datetime.now().isoformat(timespec="seconds"),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if rebuild_on_change:
            rebuilt = _rebuild_balance()
            ok = ok and rebuilt

    payload = {
        "ok": ok,
        "changed": result.changed,
        "digest": result.fingerprint.digest,
        "previous_digest": previous,
        "tab_rows": result.fingerprint.tab_rows,
        "rows_written": result.rows_written,
        "rebuilt_balance": rebuilt,
        "error": result.error,
        "live_sid": live_sid,
        "sandbox_sid": sandbox_sid,
        "interval_note": "one-way live→sandbox; full rows incl. NOTES/log",
    }
    write_heartbeat(HEARTBEAT_PATH, payload)
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Sandbox live intake mirror daemon")
    ap.add_argument("--once", action="store_true", help="Single tick then exit")
    ap.add_argument("--force", action="store_true", help="Force copy even if digest matches")
    ap.add_argument("--interval", type=int, default=None, help="Override poll interval seconds")
    ap.add_argument("--no-rebuild", action="store_true", help="Skip BALANCE rebuild on change")
    args = ap.parse_args()

    cfg = _cfg_mirror()
    if not cfg.get("enabled", True):
        _log("sandbox_mirror.enabled=false — exiting")
        return 0

    interval = int(args.interval if args.interval is not None else cfg["interval_seconds"])
    rebuild = bool(cfg["rebuild_balance_on_change"]) and not args.no_rebuild
    sa_json = cfg["service_account_json"]
    live_sid = cfg["live_sid"]
    sandbox_sid = cfg["sandbox_sid"]

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    (INSTANCE_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (INSTANCE_DIR / "health").mkdir(parents=True, exist_ok=True)
    (INSTANCE_DIR / "state").mkdir(parents=True, exist_ok=True)

    if not args.once and not _acquire_pid_lock():
        return 1

    _log(
        f"start interval={interval}s rebuild_on_change={rebuild} "
        f"live={live_sid[:8]}… sandbox={sandbox_sid[:8]}… "
        f"log={LOG_PATH}"
    )

    try:
        while True:
            try:
                run_tick(
                    force=args.force,
                    rebuild_on_change=rebuild,
                    sa_json=sa_json,
                    live_sid=live_sid,
                    sandbox_sid=sandbox_sid,
                )
            except Exception as exc:  # noqa: BLE001 — daemon must survive a bad tick
                _log(f"tick CRASHED: {exc}")
                write_heartbeat(
                    HEARTBEAT_PATH,
                    {"ok": False, "error": str(exc), "changed": False},
                )
            if args.once:
                break
            # Force only applies to the first tick.
            args.force = False
            time.sleep(max(15, interval))
    finally:
        if not args.once:
            _release_pid_lock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
