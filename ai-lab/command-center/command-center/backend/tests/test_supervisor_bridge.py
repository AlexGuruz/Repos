from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from core.ai_lab import ensure_ai_lab_root_on_path
from services import supervisor_bridge

ensure_ai_lab_root_on_path()


def test_controlled_ops_are_persisted_before_publishing_approval():
    async def run_case():
        with patch("brain.approval_queue.queue.submit", return_value="approval-9") as submit, \
             patch.object(supervisor_bridge.bus, "publish", new_callable=AsyncMock) as publish:
            result = await supervisor_bridge.route_intent(
                "command-center",
                "run_approved",
                {"script_path": "registry/foo.py", "detail": "run known script"},
            )

        assert result == {"ok": True, "queued": True, "apr_id": "approval-9", "status": "pending"}
        spec = submit.call_args.args[0]
        assert spec["supervisor_action"] == "run_approved"
        assert spec["payload"] == {"script_path": "registry/foo.py", "detail": "run known script"}
        assert publish.await_args.args[0] == "approval"
        assert publish.await_args.args[1]["id"] == "approval-9"

    asyncio.run(run_case())
