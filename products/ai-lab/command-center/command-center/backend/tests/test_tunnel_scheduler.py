"""TunnelScheduler fairness / concurrency / cancel tests."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import tunnel as tunnel_router
from services.tunnel_scheduler import TunnelOverloadError, TunnelScheduler


def test_lane_for_op():
    s = TunnelScheduler()
    assert s.lane_for_op("health") == "control"
    assert s.lane_for_op("semantic_search") == "interactive"
    assert s.lane_for_op("index_repo") == "bulk"


def test_bulk_does_not_block_control():
    s = TunnelScheduler(bulk_concurrency=1, total_concurrency=2)

    async def _run():
        await s.start()
        order: list[str] = []

        async def slow_bulk():
            order.append("bulk-start")
            await asyncio.sleep(0.25)
            order.append("bulk-end")
            return "bulk"

        async def quick_control():
            order.append("control")
            return "control"

        bulk_task = asyncio.create_task(
            s.submit("bulk", slow_bulk, timeout=5.0, op="index_repo")
        )
        await asyncio.sleep(0.02)
        ctrl = await s.submit("control", quick_control, timeout=2.0, op="health")
        await bulk_task
        assert ctrl == "control"
        assert "control" in order
        assert order.index("control") < order.index("bulk-end")
        await s.stop()

    asyncio.run(_run())


def test_queue_overload_rejects():
    s = TunnelScheduler(
        bulk_concurrency=1,
        total_concurrency=1,
        queue_limits={"control": 1, "interactive": 1, "bulk": 1},
    )

    async def _run():
        await s.start()
        gate = asyncio.Event()

        async def hang():
            await gate.wait()
            return 1

        t1 = asyncio.create_task(s.submit("interactive", hang, timeout=5.0, op="search"))
        await asyncio.sleep(0.05)
        # One running; fill the only queue slot
        t2 = asyncio.create_task(s.submit("interactive", hang, timeout=5.0, op="search"))
        await asyncio.sleep(0.05)
        with pytest.raises(TunnelOverloadError):
            await s.submit("interactive", hang, timeout=2.0, op="search")
        gate.set()
        await asyncio.gather(t1, t2, return_exceptions=True)
        await s.stop()

    asyncio.run(_run())


def test_cancel_queued_job():
    s = TunnelScheduler(bulk_concurrency=1, total_concurrency=1)

    async def _run():
        await s.start()
        gate = asyncio.Event()

        async def hang():
            await gate.wait()
            return "x"

        running = asyncio.create_task(s.submit("bulk", hang, timeout=10.0, op="index_repo"))
        await asyncio.sleep(0.05)

        async def quick():
            return "ok"

        wait_task = asyncio.create_task(s.submit("interactive", quick, timeout=2.0, op="search"))
        await asyncio.sleep(0.05)
        # Cancel the queued interactive job
        cancelled_any = False
        for jid, job in list(s._jobs.items()):
            if job.lane == "interactive":
                res = s.cancel(jid)
                cancelled_any = bool(res.get("ok")) or cancelled_any
                assert res.get("was_queued") is True
        assert cancelled_any
        with pytest.raises(asyncio.CancelledError):
            await wait_task
        gate.set()
        await asyncio.gather(running, return_exceptions=True)
        await s.stop()

    asyncio.run(_run())


def test_cancel_idle_wrong_id():
    s = TunnelScheduler()
    res = s.cancel("does-not-exist")
    assert res["ok"] is False
    assert res["reason"] == "not_found"


def test_cancel_running_job():
    s = TunnelScheduler(bulk_concurrency=1, total_concurrency=1)

    async def _run():
        await s.start()
        started = asyncio.Event()

        async def hang():
            started.set()
            await asyncio.sleep(30)
            return "late"

        job_ids: list[str] = []
        task = asyncio.create_task(
            s.submit("bulk", hang, timeout=60.0, op="index_repo", on_enqueued=job_ids.append)
        )
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert job_ids
        jid = job_ids[0]
        listed = s.list_jobs()
        assert any(j["job_id"] == jid and j["status"] == "running" for j in listed)
        res = s.cancel(jid)
        assert res["ok"] is True
        assert res["was_running"] is True
        with pytest.raises(asyncio.CancelledError):
            await task
        await s.stop()

    asyncio.run(_run())


def test_cancel_http_wrong_id_and_list():
    """API: cancel wrong id → 404; list idle ok."""
    from services import tunnel_scheduler as ts_mod

    s = TunnelScheduler()
    old = ts_mod.tunnel_scheduler
    ts_mod.tunnel_scheduler = s
    tunnel_router.tunnel_scheduler = s
    app = FastAPI()
    app.include_router(tunnel_router.router)
    client = TestClient(app)
    try:
        r = client.post("/api/tunnel/jobs/not-a-real-job/cancel")
        assert r.status_code == 404
        idle = client.get("/api/tunnel/jobs")
        assert idle.status_code == 200
        assert idle.json()["ok"] is True
        assert idle.json()["jobs"] == []
    finally:
        ts_mod.tunnel_scheduler = old
        tunnel_router.tunnel_scheduler = old
