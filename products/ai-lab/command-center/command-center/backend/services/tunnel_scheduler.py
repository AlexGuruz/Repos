"""
Fair priority scheduler for supervisor / SSH / worker tunnel work.

Lanes (highest first, with fairness so bulk cannot starve interactive/control):
  control → interactive → bulk
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from services.observability import log_error, log_metric

Lane = Literal["control", "interactive", "bulk"]

_LANE_PRIORITY = {"control": 0, "interactive": 1, "bulk": 2}

_DEFAULT_BULK_CONCURRENCY = 1
_DEFAULT_TOTAL_CONCURRENCY = 3
_DEFAULT_QUEUE = {"control": 32, "interactive": 64, "bulk": 16}
_DEFAULT_TIMEOUTS = {"control": 30.0, "interactive": 120.0, "bulk": 900.0}


class TunnelOverloadError(Exception):
    def __init__(self, lane: Lane, reason: str = "queue_full"):
        super().__init__(f"TunnelScheduler overloaded on lane '{lane}': {reason}")
        self.lane = lane
        self.reason = reason


@dataclass
class _Job:
    job_id: str
    lane: Lane
    coro_factory: Callable[[], Awaitable[Any]]
    timeout: float
    future: asyncio.Future
    op: str = ""
    enqueued_at: float = field(default_factory=time.monotonic)
    cancelled: bool = False
    started_at: float | None = None


class TunnelScheduler:
    def __init__(
        self,
        *,
        bulk_concurrency: int = _DEFAULT_BULK_CONCURRENCY,
        total_concurrency: int = _DEFAULT_TOTAL_CONCURRENCY,
        queue_limits: dict[str, int] | None = None,
        timeouts: dict[str, float] | None = None,
    ) -> None:
        self.bulk_concurrency = bulk_concurrency
        self.total_concurrency = total_concurrency
        self.queue_limits = queue_limits or dict(_DEFAULT_QUEUE)
        self.timeouts = timeouts or dict(_DEFAULT_TIMEOUTS)
        self._queues: dict[Lane, list[_Job]] = {
            "control": [],
            "interactive": [],
            "bulk": [],
        }
        self._wakeup = asyncio.Event()
        self._active = 0
        self._active_bulk = 0
        self._worker: asyncio.Task | None = None
        self._running_tasks: set[asyncio.Task] = set()
        self._running_by_job: dict[str, asyncio.Task] = {}
        self._jobs: dict[str, _Job] = {}
        self._rr = 0
        self.metrics: dict[str, Any] = {
            "submitted": 0,
            "completed": 0,
            "timeouts": 0,
            "cancellations": 0,
            "rejections": 0,
            "by_lane": {k: {"submitted": 0, "completed": 0, "timeouts": 0, "rejected": 0} for k in _LANE_PRIORITY},
        }

    def _ensure_worker(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._worker is None or self._worker.done():
            self._wakeup = asyncio.Event()
            self._worker = loop.create_task(self._run(), name="tunnel-scheduler")

    async def start(self) -> None:
        self._ensure_worker()

    async def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            self._worker = None
        for task in list(self._running_tasks):
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._running_tasks.clear()
        self._running_by_job.clear()

    def lane_for_op(self, op: str) -> Lane:
        o = (op or "").strip().lower()
        if o in {"health", "ready", "live", "status", "ping", "cancel", "smoke", "repo_status"}:
            return "control"
        if o in {"index_repo", "promote_repo_index", "embed"}:
            return "bulk"
        return "interactive"

    async def submit(
        self,
        lane: Lane,
        coro_factory: Callable[[], Awaitable[Any]],
        *,
        timeout: float | None = None,
        op: str = "",
        on_enqueued: Callable[[str], None] | None = None,
    ) -> Any:
        self._ensure_worker()
        q = self._queues[lane]
        if len(q) >= self.queue_limits[lane]:
            self.metrics["rejections"] += 1
            self.metrics["by_lane"][lane]["rejected"] += 1
            log_metric("tunnel_reject", lane=lane, op=op, depth=len(q))
            raise TunnelOverloadError(lane)

        job_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        fut: asyncio.Future = loop.create_future()
        job = _Job(
            job_id=job_id,
            lane=lane,
            coro_factory=coro_factory,
            timeout=float(timeout if timeout is not None else self.timeouts[lane]),
            future=fut,
            op=op or "",
        )
        q.append(job)
        self._jobs[job_id] = job
        self.metrics["submitted"] += 1
        self.metrics["by_lane"][lane]["submitted"] += 1
        log_metric("tunnel_submit", lane=lane, op=op, job_id=job_id)
        if on_enqueued is not None:
            try:
                on_enqueued(job_id)
            except Exception:
                pass
        self._wakeup.set()
        try:
            return await fut
        finally:
            self._jobs.pop(job_id, None)
            self._running_by_job.pop(job_id, None)

    def cancel(self, job_id: str) -> dict[str, Any]:
        """
        Cancel a queued or in-flight tunnel job (local scheduler).
        Remote WA cooperative abort is not guaranteed (soft cancel).
        Returns a dict with ok/reason for HTTP mapping.
        """
        jid = (job_id or "").strip()
        if not jid:
            return {"ok": False, "reason": "missing_id", "job_id": jid}
        job = self._jobs.get(jid)
        if not job:
            return {"ok": False, "reason": "not_found", "job_id": jid}

        was_queued = job in self._queues[job.lane]
        was_running = jid in self._running_by_job and not self._running_by_job[jid].done()
        job.cancelled = True
        if was_queued:
            self._queues[job.lane].remove(job)

        task = self._running_by_job.get(jid)
        if task is not None and not task.done():
            task.cancel()

        if not job.future.done():
            job.future.cancel()

        self.metrics["cancellations"] += 1
        log_metric("tunnel_cancel", lane=job.lane, op=job.op, job_id=jid, was_queued=was_queued, was_running=was_running)
        self._wakeup.set()
        return {
            "ok": True,
            "job_id": jid,
            "lane": job.lane,
            "op": job.op,
            "was_queued": was_queued,
            "was_running": was_running,
            "remote_abort": "soft",
            "note": "Local scheduler cancel; remote Worker Assistant may continue until its own timeout.",
        }

    def list_jobs(self) -> list[dict[str, Any]]:
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        for jid, job in list(self._jobs.items()):
            running = jid in self._running_by_job and not self._running_by_job[jid].done()
            queued = job in self._queues[job.lane]
            status = "running" if running else ("queued" if queued else "finishing")
            out.append(
                {
                    "job_id": jid,
                    "lane": job.lane,
                    "op": job.op,
                    "status": status,
                    "cancelled": job.cancelled,
                    "age_ms": int((now - job.enqueued_at) * 1000),
                    "started_age_ms": int((now - job.started_at) * 1000) if job.started_at else None,
                }
            )
        out.sort(key=lambda r: (0 if r["status"] == "running" else 1, -int(r["age_ms"] or 0)))
        return out

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        jid = (job_id or "").strip()
        for row in self.list_jobs():
            if row["job_id"] == jid:
                return row
        return None

    def _can_start(self, lane: Lane) -> bool:
        if self._active >= self.total_concurrency:
            return False
        if lane == "bulk" and self._active_bulk >= self.bulk_concurrency:
            return False
        return True

    def _pick_job(self) -> _Job | None:
        self._rr += 1
        # Fairness: every 4th cycle, try interactive before bulk after control.
        order: list[Lane] = ["control", "interactive", "bulk"]
        for lane in order:
            if not self._can_start(lane):
                continue
            q = self._queues[lane]
            while q:
                job = q.pop(0)
                if job.cancelled:
                    if not job.future.done():
                        job.future.cancel()
                    continue
                return job
        return None

    async def _run(self) -> None:
        while True:
            job = self._pick_job()
            if job is None:
                self._wakeup.clear()
                # Wait for submit or a short tick so capacity frees up.
                try:
                    await asyncio.wait_for(self._wakeup.wait(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass
                continue
            task = asyncio.create_task(self._execute(job))
            self._running_tasks.add(task)
            self._running_by_job[job.job_id] = task
            task.add_done_callback(self._running_tasks.discard)

    async def _execute(self, job: _Job) -> None:
        self._active += 1
        if job.lane == "bulk":
            self._active_bulk += 1
        job.started_at = time.monotonic()
        t0 = job.started_at
        try:
            if job.cancelled:
                if not job.future.done():
                    job.future.cancel()
                return
            result = await asyncio.wait_for(job.coro_factory(), timeout=job.timeout)
            if not job.future.done():
                job.future.set_result(result)
            self.metrics["completed"] += 1
            self.metrics["by_lane"][job.lane]["completed"] += 1
            log_metric(
                "tunnel_complete",
                lane=job.lane,
                duration_ms=int((time.monotonic() - t0) * 1000),
                wait_ms=int((t0 - job.enqueued_at) * 1000),
            )
        except asyncio.TimeoutError:
            self.metrics["timeouts"] += 1
            self.metrics["by_lane"][job.lane]["timeouts"] += 1
            log_error("tunnel", "timeout", lane=job.lane, job_id=job.job_id)
            if not job.future.done():
                job.future.set_exception(TimeoutError(f"tunnel {job.lane} timed out after {job.timeout}s"))
        except asyncio.CancelledError:
            # cancel() already increments cancellations; avoid double-count when task cancelled.
            if not job.cancelled:
                self.metrics["cancellations"] += 1
            if not job.future.done():
                job.future.cancel()
        except Exception as exc:
            log_error("tunnel", "job_failed", lane=job.lane, error=str(exc)[:200])
            if not job.future.done():
                job.future.set_exception(exc)
        finally:
            self._active -= 1
            if job.lane == "bulk":
                self._active_bulk -= 1
            self._running_by_job.pop(job.job_id, None)
            self._wakeup.set()

    def snapshot(self) -> dict[str, Any]:
        return {
            "active": self._active,
            "active_bulk": self._active_bulk,
            "queue_depths": {k: len(v) for k, v in self._queues.items()},
            "jobs": self.list_jobs(),
            "metrics": self.metrics,
        }


tunnel_scheduler = TunnelScheduler()
