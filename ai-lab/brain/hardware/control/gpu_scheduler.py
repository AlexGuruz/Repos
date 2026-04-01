"""
GPU workload scheduling (Guru §25). Queue/noncritical job gating; stub.
"""
from __future__ import annotations


def queue_gpu_job(job_id: str, priority: str = "normal") -> dict[str, str | bool]:
    """Queue a noncritical GPU job. Stub."""
    _ = job_id
    _ = priority
    return {"ok": False, "error": "GPU job queue not yet implemented."}
