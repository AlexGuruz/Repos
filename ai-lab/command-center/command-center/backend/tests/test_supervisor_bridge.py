from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from services import supervisor_bridge


def test_controlled_op_persists_resolvable_approval_before_publishing():
    supervisor_bridge._ensure_brain_path()

    with patch("brain.approval_queue.queue.submit", return_value="approval-11") as submit, \
         patch.object(supervisor_bridge, "_catalog_attachment_from_payload", return_value=None), \
         patch.object(supervisor_bridge.bus, "publish", new_callable=AsyncMock) as publish:
        result = asyncio.run(
            supervisor_bridge.route_intent(
                "command-center",
                "run_approved",
                {"script_path": "registry/foo.py", "detail": "Run registered script"},
            )
        )

    assert result == {"ok": True, "queued": True, "apr_id": "approval-11", "status": "pending"}
    submitted = submit.call_args.args[0]
    assert submitted["supervisor_action"] == "run_approved"
    assert submitted["supervisor_payload"] == {
        "script_path": "registry/foo.py",
        "detail": "Run registered script",
    }
    published = publish.await_args.args[1]
    assert published["id"] == "approval-11"
    assert published["payload"] == {"script_path": "registry/foo.py", "detail": "Run registered script"}
