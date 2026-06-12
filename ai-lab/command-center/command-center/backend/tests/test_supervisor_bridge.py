from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from services import supervisor_bridge


def test_controlled_op_is_not_bypassed_by_worker_read_extra():
    supervisor_bridge._PENDING_CONTROLLED_APPROVALS.clear()
    try:
        with patch.object(supervisor_bridge.settings, "worker_read_ops_extra", "run_approved"), \
             patch.object(supervisor_bridge, "_worker_call", new=AsyncMock()) as worker_call, \
             patch.object(supervisor_bridge.bus, "publish", new=AsyncMock()):
            result = asyncio.run(
                supervisor_bridge.route_intent(
                    "command-center",
                    "run_approved",
                    {"tool_name": "safe_tool", "detail": "run safe tool"},
                )
            )

        assert result["ok"] is True
        assert result["queued"] is True
        assert result["apr_id"].startswith("APR-")
        assert result["apr_id"] in supervisor_bridge._PENDING_CONTROLLED_APPROVALS
        worker_call.assert_not_awaited()
    finally:
        supervisor_bridge._PENDING_CONTROLLED_APPROVALS.clear()
