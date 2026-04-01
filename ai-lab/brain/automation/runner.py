"""
Job runner (PDR Phase 3). Executes automation jobs: scheduled, manual, dry-run.
Skeleton: run_job does nothing until wired to connector execution.
"""
from __future__ import annotations

from typing import Any


def run_job(job_id: str, dry_run: bool = False) -> dict[str, Any]:
    """
    Run an automation job by id. If dry_run=True, validate and report only.
    Returns: status, output, error (if any).
    """
    _ = job_id
    _ = dry_run
    return {"status": "not_implemented", "output": "", "error": "Job runner is a stub."}


def list_jobs() -> list[dict[str, Any]]:
    """List registered automation jobs. Stub returns empty."""
    return []
