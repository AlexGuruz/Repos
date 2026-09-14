from __future__ import annotations

import asyncio

from routers import retail


def test_retail_router_exposes_unavailable_status_without_startup_failure():
    assert any(route.path == "/api/retail/health" for route in retail.router.routes)

    body = asyncio.run(retail.retail_health())
    assert body["ok"] is False
    assert body["status"] == "unavailable"
    assert body["kind"] == "health"
