#!/usr/bin/env python3
"""
Platform orchestrator — scheduled refresh of facts + domain latest JSON + status.

Kinds:
  ingest | dashboard | consignment_json | capital | full | status

Does not call Desk refresh from AI paths; this is the ops/scheduler entrypoint.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.platform_config import load_platform_config  # noqa: E402
from lib.platform_status import write_platform_status  # noqa: E402


@dataclass
class PlatformJob:
    id: str
    org_id: str
    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    print(">>", " ".join(cmd), flush=True)
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(cwd)}
    r = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "exit_code": r.returncode,
        "stdout_tail": (r.stdout or "")[-3000:],
        "stderr_tail": (r.stderr or "")[-2000:],
    }


def run_job(job: PlatformJob) -> PlatformJob:
    cfg = load_platform_config()
    job.org_id = job.org_id or cfg.org_id
    job.started_at = _now()
    job.status = "running"
    py = sys.executable
    kind = job.kind
    params = job.params
    days = int(params.get("days") or 30)
    preset = str(params.get("preset") or "last_30_days")

    steps: list[list[str]] = []
    if kind in ("ingest", "full"):
        steps.append([py, str(REPO / "scripts" / "ingest_growflow_facts.py"), "--days", str(days)])
    if kind in ("dashboard", "full"):
        cmd = [py, str(REPO / "scripts" / "build_retail_dashboard.py"), "--preset", preset, "--strict"]
        if params.get("compare", True):
            cmd.append("--compare")
        if params.get("reconcile", True):
            cmd.append("--reconcile")
        steps.append(cmd)
    if kind in ("consignment_json", "full"):
        steps.append([py, str(REPO / "scripts" / "build_retail_consignment.py")])
    if kind in ("capital", "full") and params.get("rebuild_capital", True):
        steps.append([py, str(REPO / "scripts" / "build_retail_capital.py")])
    if kind == "status" or True:
        # always refresh status at end
        pass

    for cmd in steps:
        result = _run(cmd, cwd=REPO)
        job.steps.append(result)
        if result["exit_code"] != 0:
            job.status = "failed"
            job.finished_at = _now()
            write_platform_status(cfg=cfg)
            return job

    status_result = _run([py, str(REPO / "scripts" / "build_platform_status.py")], cwd=REPO)
    job.steps.append(status_result)
    job.status = "completed" if status_result["exit_code"] in (0, 1) else "failed"
    # exit 1 from status means SLO breaches but script ran — treat orchestrator ok if builds passed
    if status_result["exit_code"] not in (0, 1):
        job.status = "failed"
    else:
        job.status = "completed"
    job.finished_at = _now()
    write_platform_status(cfg=cfg)
    return job


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Growflow platform orchestrator")
    ap.add_argument(
        "--kind",
        default="full",
        choices=["ingest", "dashboard", "consignment_json", "capital", "full", "status"],
    )
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--preset", default="last_30_days")
    ap.add_argument("--no-compare", action="store_true")
    ap.add_argument("--no-reconcile", action="store_true")
    ap.add_argument("--no-capital", action="store_true")
    ap.add_argument("--org-id", default=None)
    args = ap.parse_args(argv)

    cfg = load_platform_config()
    job = PlatformJob(
        id=f"plat_{uuid4().hex[:10]}",
        org_id=args.org_id or cfg.org_id,
        kind=args.kind,
        params={
            "days": args.days,
            "preset": args.preset,
            "compare": not args.no_compare,
            "reconcile": not args.no_reconcile,
            "rebuild_capital": not args.no_capital,
        },
    )
    if args.kind == "status":
        write_platform_status(cfg=cfg)
        print(json.dumps({"job_id": job.id, "status": "completed", "kind": "status"}))
        return 0

    job = run_job(job)
    print(json.dumps({"job_id": job.id, "status": job.status, "kind": job.kind, "steps": len(job.steps)}))
    # Emit lightweight event file for CC feed bus consumers
    events_dir = cfg.data_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "dashboard_run_completed" if job.status == "completed" else "dashboard_run_failed",
        "job": asdict(job),
        "emitted_at": _now(),
    }
    (events_dir / f"{job.id}.json").write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    latest_event = events_dir / "latest.json"
    latest_event.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    return 0 if job.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
