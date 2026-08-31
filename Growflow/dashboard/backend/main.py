"""
Retail dashboard API — localhost only (port 8791).

Serves pre-built aggregates from retail_dashboard.db / latest JSON.
Refresh triggers ingest + build scripts as background subprocess.

Approval pattern (Command Center):
  POST /api/retail/capital/scenario with skip_approval=false stores pending spec;
  ai-lab publishes sidebar APR event; approve calls /capital/scenario/{id}/execute.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.growflow_fact_store import DEFAULT_DB_PATH, connect as facts_connect, init_db as facts_init
from lib.platform_config import load_platform_config
from lib.platform_status import enrich_retail_payload, load_platform_status, write_platform_status
from lib.retail_dashboard.cache import DEFAULT_CACHE_PATH, connect_cache, load_latest, load_run
from lib.retail_dashboard.capital import (
    DEFAULT_CAPITAL_JSON,
    DEFAULT_LAYER2_CSV,
    build_capital,
    payload_to_dict,
)
from lib.retail_dashboard.consignment import (
    DEFAULT_CONSIGNMENT_JSON,
    build_consignment,
    payload_to_dict as consignment_to_dict,
    consignment_db_path,
    enrich_consignment_dict,
)
from lib.retail_dashboard.reconcile import (
    DEFAULT_REPORT_JSON,
    load_reconciliation_report,
    reconciliation_status_summary,
)

HOST = "127.0.0.1"
PORT = 8791

_platform_cfg = load_platform_config()
LATEST_JSON = _platform_cfg.retail_dashboard_json
PROJECTION_JSON = _platform_cfg.sales_projection_json
COMPANY_BI_JSON = _platform_cfg.company_bi_json
EVENTS_LATEST = _platform_cfg.data_dir / "events" / "latest.json"

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_pending_capital: dict[str, dict[str, Any]] = {}
_pending_capital_lock = threading.Lock()

app = FastAPI(title="Growflow Ops Platform API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _enrich_dashboard(data: dict[str, Any]) -> dict[str, Any]:
    return enrich_retail_payload(data, cfg=_platform_cfg, source_path=LATEST_JSON)


def _read_json_path(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _emit_job_event(job_id: str, status: str, job_type: str = "refresh") -> None:
    events_dir = _platform_cfg.data_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "dashboard_run_completed" if status == "completed" else "dashboard_run_failed",
        "job_id": job_id,
        "job_type": job_type,
        "status": status,
        "emitted_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "org_id": _platform_cfg.org_id,
    }
    (events_dir / f"{job_id}.json").write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")
    EVENTS_LATEST.write_text(json.dumps(event, indent=2) + "\n", encoding="utf-8")



class RefreshRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    preset: str = Field(default="last_30_days")
    compare: bool = True
    store_id: str | None = None
    channel: str = "all"


class CapitalScenarioRequest(BaseModel):
    pool_usd: float = Field(default=18000.0, ge=1000, le=500_000)
    velocity_days: int = Field(default=49, ge=7, le=365)
    cash_cycle_days: int = Field(default=14, ge=7, le=90)
    allocation_mode: str = Field(default="buy-plan")
    days: int = Field(default=365, ge=30, le=730)
    skip_approval: bool = Field(default=False)


def _read_latest_json() -> dict[str, Any] | None:
    if not LATEST_JSON.is_file():
        return None
    try:
        return json.loads(LATEST_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_capital_json() -> dict[str, Any] | None:
    if not DEFAULT_CAPITAL_JSON.is_file():
        return None
    try:
        return json.loads(DEFAULT_CAPITAL_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_consignment_json() -> dict[str, Any] | None:
    if not DEFAULT_CONSIGNMENT_JSON.is_file():
        return None
    try:
        return json.loads(DEFAULT_CONSIGNMENT_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _run_refresh_job(job_id: str, req: RefreshRequest) -> None:
    py = sys.executable
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(REPO)}
    ingest_cmd = [py, str(REPO / "scripts" / "ingest_growflow_facts.py"), "--days", str(req.days)]
    build_cmd = [py, str(REPO / "scripts" / "build_retail_dashboard.py"), "--preset", req.preset]
    if req.compare:
        build_cmd.append("--compare")
    if req.store_id:
        build_cmd.extend(["--store-id", req.store_id])
    if req.channel and req.channel != "all":
        build_cmd.extend(["--channel", req.channel])

    with _jobs_lock:
        _jobs[job_id]["status"] = "ingesting"
        _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        r1 = subprocess.run(ingest_cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
        with _jobs_lock:
            _jobs[job_id]["ingest_exit"] = r1.returncode
            _jobs[job_id]["ingest_log"] = (r1.stdout or "")[-4000:] + (r1.stderr or "")[-2000:]
        if r1.returncode != 0:
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "ingest failed"
            return

        with _jobs_lock:
            _jobs[job_id]["status"] = "building"

        r2 = subprocess.run(build_cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
        with _jobs_lock:
            _jobs[job_id]["build_exit"] = r2.returncode
            _jobs[job_id]["build_log"] = (r2.stdout or "")[-4000:] + (r2.stderr or "")[-2000:]
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            if r2.returncode == 0:
                _jobs[job_id]["status"] = "completed"
                try:
                    write_platform_status(cfg=_platform_cfg)
                except Exception:
                    pass
                _emit_job_event(job_id, "completed", "refresh")
            else:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "build failed"
                _emit_job_event(job_id, "failed", "refresh")
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        _emit_job_event(job_id, "failed", "refresh")


def _run_capital_scenario_job(job_id: str, req: CapitalScenarioRequest) -> None:
    py = sys.executable
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(REPO)}
    layer2_out = DEFAULT_LAYER2_CSV
    proj_cmd = [
        py,
        str(REPO / "scripts" / "build_projection_by_category_brand.py"),
        "--pool",
        str(req.pool_usd),
        "--velocity-days",
        str(req.velocity_days),
        "--cash-cycle-days",
        str(req.cash_cycle_days),
        "--allocation-mode",
        req.allocation_mode,
        "--days",
        str(req.days),
        "--layer2-csv",
        str(layer2_out),
        "--validation-mode",
        "warning",
    ]
    cap_cmd = [py, str(REPO / "scripts" / "build_retail_capital.py"), "--layer2-csv", str(layer2_out)]

    with _jobs_lock:
        _jobs[job_id]["status"] = "running_projection"
        _jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        r1 = subprocess.run(proj_cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
        with _jobs_lock:
            _jobs[job_id]["projection_exit"] = r1.returncode
            _jobs[job_id]["projection_log"] = (r1.stdout or "")[-6000:] + (r1.stderr or "")[-3000:]
        if r1.returncode != 0:
            with _jobs_lock:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "projection build failed"
            return

        with _jobs_lock:
            _jobs[job_id]["status"] = "building_capital"

        r2 = subprocess.run(cap_cmd, cwd=str(REPO), env=env, capture_output=True, text=True)
        with _jobs_lock:
            _jobs[job_id]["capital_exit"] = r2.returncode
            _jobs[job_id]["capital_log"] = (r2.stdout or "")[-2000:]
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            if r2.returncode == 0:
                _jobs[job_id]["status"] = "completed"
                try:
                    write_platform_status(cfg=_platform_cfg)
                except Exception:
                    pass
                _emit_job_event(job_id, "completed", "capital_scenario")
            else:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = "capital build failed"
                _emit_job_event(job_id, "failed", "capital_scenario")
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
            _jobs[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
        _emit_job_event(job_id, "failed", "capital_scenario")


def _start_capital_job(req: CapitalScenarioRequest, *, job_id: str | None = None) -> dict[str, Any]:
    jid = job_id or f"cap_{uuid.uuid4().hex[:10]}"
    with _jobs_lock:
        existing = _jobs.get(jid)
        if existing:
            existing.update({"status": "queued", "request": req.model_dump()})
        else:
            _jobs[jid] = {
                "job_id": jid,
                "job_type": "capital_scenario",
                "status": "queued",
                "request": req.model_dump(),
            }
    t = threading.Thread(target=_run_capital_scenario_job, args=(jid, req), daemon=True)
    t.start()
    return {"job_id": jid, "status": "queued", "approval_required": False}


@app.get("/api/health")
def health():
    status = load_platform_status(_platform_cfg)
    return {
        "ok": True,
        "org_id": _platform_cfg.org_id,
        "facts_db": str(DEFAULT_DB_PATH),
        "facts_db_exists": DEFAULT_DB_PATH.is_file(),
        "cache_db_exists": DEFAULT_CACHE_PATH.is_file(),
        "latest_json_exists": LATEST_JSON.is_file(),
        "capital_json_exists": DEFAULT_CAPITAL_JSON.is_file(),
        "consignment_json_exists": DEFAULT_CONSIGNMENT_JSON.is_file(),
        "layer2_csv_exists": DEFAULT_LAYER2_CSV.is_file(),
        "reconciliation_json_exists": DEFAULT_REPORT_JSON.is_file(),
        "platform_status_exists": _platform_cfg.platform_status_json.is_file(),
        "pending_capital_approvals": len(_pending_capital),
        "platform_overall_ok": status.get("overall_ok"),
        "slo_breaches": status.get("slo_breaches") or [],
    }


@app.get("/api/v1/platform/health")
def platform_health_v1():
    status = load_platform_status(_platform_cfg)
    return {
        "ok": True,
        "process": "alive",
        "org_id": _platform_cfg.org_id,
        "status": status,
        "latest_event": _read_json_path(EVENTS_LATEST),
    }


@app.get("/api/v1/platform/events/latest")
def platform_events_latest():
    event = _read_json_path(EVENTS_LATEST)
    if not event:
        raise HTTPException(404, "No platform events yet")
    return event


@app.get("/api/v1/projection")
def projection_v1():
    payload = _read_json_path(PROJECTION_JSON)
    if not payload:
        raise HTTPException(404, "No sales_projection_latest.json — run run_daily_sales_projection.py")
    meta = {
        "org_id": _platform_cfg.org_id,
        "path": str(PROJECTION_JSON),
        "as_of_local": payload.get("as_of_local"),
        "sales_date": payload.get("sales_date"),
    }
    out = dict(payload)
    out["meta"] = {**(payload.get("meta") if isinstance(payload.get("meta"), dict) else {}), **meta}
    out["trust"] = {
        "org_id": _platform_cfg.org_id,
        "source_paths": [str(PROJECTION_JSON)],
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    return out


@app.get("/api/v1/bi")
def bi_v1():
    payload = _read_json_path(COMPANY_BI_JSON)
    if not payload:
        raise HTTPException(
            404,
            "No company_bi_report_latest.json — run scripts/build_company_bi_report.py "
            "(not company_bi.run_pipeline)",
        )
    out = dict(payload)
    meta = dict(out.get("meta") or {}) if isinstance(out.get("meta"), dict) else {}
    meta["org_id"] = meta.get("org_id") or _platform_cfg.org_id
    out["meta"] = meta
    return out


@app.get("/api/v1/retail/dashboard")
def retail_dashboard_v1(run_id: str | None = Query(default=None)):
    return get_dashboard(run_id=run_id)


@app.get("/api/v1/retail/capital")
def retail_capital_v1():
    return get_capital()


@app.get("/api/v1/retail/consignment")
def retail_consignment_v1():
    return get_consignment()


@app.get("/api/retail/reconciliation")
def get_reconciliation():
    report = load_reconciliation_report(DEFAULT_REPORT_JSON)
    return reconciliation_status_summary(report)


@app.get("/api/retail/dashboard")
def get_dashboard(run_id: str | None = Query(default=None)):
    if run_id:
        conn = connect_cache()
        try:
            data = load_run(conn, run_id)
        finally:
            conn.close()
        if not data:
            raise HTTPException(404, f"run not found: {run_id}")
        return _enrich_dashboard(data)

    conn = connect_cache()
    try:
        data = load_latest(conn)
    finally:
        conn.close()
    if data:
        return _enrich_dashboard(data)

    fallback = _read_latest_json()
    if fallback:
        return _enrich_dashboard(fallback)
    raise HTTPException(404, "No dashboard built yet — POST /api/retail/refresh")


@app.get("/api/retail/capital")
def get_capital():
    cached = _read_capital_json()
    if cached:
        meta = dict(cached.get("meta") or {})
        meta["org_id"] = meta.get("org_id") or _platform_cfg.org_id
        cached = dict(cached)
        cached["meta"] = meta
        return cached
    payload = build_capital()
    data = payload_to_dict(payload)
    if not data["meta"].get("source_exists"):
        raise HTTPException(
            404,
            "No capital projection — run build_projection_by_category_brand.py or approve a scenario",
        )
    data["meta"]["org_id"] = _platform_cfg.org_id
    return data


@app.get("/api/retail/consignment")
def get_consignment():
    cached = _read_consignment_json()
    db = consignment_db_path()
    if cached:
        stale = cached.get("meta", {}).get("source_exists") is True and not db.is_file()
        if not stale:
            data = enrich_consignment_dict(cached)
            meta = dict(data.get("meta") or {})
            meta["org_id"] = meta.get("org_id") or _platform_cfg.org_id
            data["meta"] = meta
            return data
    if not db.is_file():
        data = consignment_to_dict(build_consignment(db_path=db))
    else:
        data = consignment_to_dict(build_consignment(db_path=db))
    meta = dict(data.get("meta") or {})
    meta["org_id"] = meta.get("org_id") or _platform_cfg.org_id
    data["meta"] = meta
    return data


@app.get("/api/retail/capital/pending")
def list_pending_capital():
    with _pending_capital_lock:
        items = list(_pending_capital.values())
    return {"pending": items, "count": len(items)}


@app.post("/api/retail/capital/scenario")
def capital_scenario(req: CapitalScenarioRequest):
    if req.allocation_mode not in ("buy-plan", "throughput", "gross-share"):
        raise HTTPException(400, "allocation_mode must be buy-plan, throughput, or gross-share")

    if req.skip_approval:
        return _start_capital_job(req)

    job_id = f"cap_{uuid.uuid4().hex[:10]}"
    approval_id = f"APR-cap-{uuid.uuid4().hex[:8]}"
    spec = {
        "approval_id": approval_id,
        "job_id": job_id,
        "scenario": req.model_dump(),
        "expected_output": DEFAULT_CAPITAL_JSON.relative_to(REPO).as_posix(),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    with _pending_capital_lock:
        _pending_capital[approval_id] = spec
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "job_type": "capital_scenario",
            "status": "awaiting_approval",
            "approval_id": approval_id,
            "request": req.model_dump(),
        }
    return {
        "job_id": job_id,
        "approval_id": approval_id,
        "status": "awaiting_approval",
        "approval_required": True,
        "expected_output": spec["expected_output"],
        "summary": {
            "pool_usd": req.pool_usd,
            "velocity_days": req.velocity_days,
            "cash_cycle_days": req.cash_cycle_days,
            "allocation_mode": req.allocation_mode,
        },
    }


@app.post("/api/retail/capital/scenario/{approval_id}/execute")
def execute_capital_scenario(approval_id: str):
    with _pending_capital_lock:
        spec = _pending_capital.pop(approval_id, None)
    if not spec:
        raise HTTPException(404, f"approval not found or already resolved: {approval_id}")
    scenario = CapitalScenarioRequest(**{**spec["scenario"], "skip_approval": True})
    job_id = str(spec["job_id"])
    result = _start_capital_job(scenario, job_id=job_id)
    return {"ok": True, "approval_id": approval_id, "resolution": "approved", **result}


@app.post("/api/retail/capital/scenario/{approval_id}/deny")
def deny_capital_scenario(approval_id: str):
    with _pending_capital_lock:
        spec = _pending_capital.pop(approval_id, None)
    if not spec:
        raise HTTPException(404, f"approval not found or already resolved: {approval_id}")
    job_id = spec.get("job_id")
    if job_id:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "denied"
    return {"ok": True, "approval_id": approval_id, "resolution": "denied"}


@app.get("/api/retail/stores")
def list_stores():
    if not DEFAULT_DB_PATH.is_file():
        return {"stores": []}
    conn = facts_connect()
    facts_init(conn)
    rows = conn.execute("SELECT object_id, name FROM stores ORDER BY name").fetchall()
    conn.close()
    return {"stores": [{"id": r["object_id"], "name": r["name"]} for r in rows]}


@app.post("/api/retail/refresh")
def refresh(req: RefreshRequest):
    job_id = f"job_{uuid.uuid4().hex[:10]}"
    with _jobs_lock:
        _jobs[job_id] = {"job_id": job_id, "status": "queued", "request": req.model_dump()}
    t = threading.Thread(target=_run_refresh_job, args=(job_id, req), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/retail/jobs/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dashboard.backend.main:app", host=HOST, port=PORT, reload=False)
