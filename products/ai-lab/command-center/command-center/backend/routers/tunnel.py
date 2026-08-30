"""Public tunnel scheduler surfaces: list + cancel jobs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services.observability import log_api
from services.tunnel_scheduler import tunnel_scheduler

router = APIRouter()


@router.get("/api/tunnel/jobs")
async def list_tunnel_jobs():
    jobs = tunnel_scheduler.list_jobs()
    log_api("tunnel", "list_jobs", count=len(jobs))
    return {"ok": True, "jobs": jobs, "snapshot": tunnel_scheduler.snapshot()}


@router.get("/api/tunnel/jobs/{job_id}")
async def get_tunnel_job(job_id: str):
    row = tunnel_scheduler.get_job(job_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Tunnel job '{job_id}' not found (idle or already finished).")
    return {"ok": True, "job": row}


@router.post("/api/tunnel/jobs/{job_id}/cancel")
async def cancel_tunnel_job(job_id: str):
    """
    Cancel a queued or in-flight TunnelScheduler job.
    Soft cancel for remote WA work — local task is aborted; remote may finish until timeout.
    """
    result = tunnel_scheduler.cancel(job_id)
    if not result.get("ok"):
        reason = result.get("reason") or "not_found"
        if reason == "missing_id":
            raise HTTPException(status_code=400, detail="job_id required")
        raise HTTPException(
            status_code=404,
            detail=f"Tunnel job '{job_id}' not found (idle, wrong id, or already finished).",
        )
    log_api(
        "tunnel",
        "cancel",
        job_id=result.get("job_id"),
        lane=result.get("lane"),
        was_queued=result.get("was_queued"),
        was_running=result.get("was_running"),
    )
    return result
