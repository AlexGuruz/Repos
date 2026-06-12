from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from services import supervisor_bridge


def test_controlled_op_publishes_persisted_approval_id():
    with patch("brain.permanent_allowlist.approval_payload_subset", return_value={"script_path": "registry/foo.py"}), \
         patch("brain.permanent_allowlist.find_matching_rule", return_value=None), \
         patch("brain.approval_queue.queue.submit", return_value="approval-42") as submit, \
         patch.object(supervisor_bridge.bus, "publish", new_callable=AsyncMock) as publish:
        result = asyncio.run(
            supervisor_bridge.route_intent(
                "command-center",
                "run_approved",
                {"script_path": "registry/foo.py", "detail": "run foo"},
            )
        )

    assert result == {"ok": True, "queued": True, "apr_id": "approval-42", "status": "pending"}
    submit.assert_called_once()
    publish.assert_awaited_once()
    event_name, event_payload = publish.await_args.args
    assert event_name == "approval"
    assert event_payload["id"] == "approval-42"
    assert event_payload["payload"] == {"script_path": "registry/foo.py"}
