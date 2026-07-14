from __future__ import annotations

import json

from brain.approval_queue import queue


def test_approval_ids_are_not_reused_after_queue_drains(tmp_path, monkeypatch) -> None:
    log_dir = tmp_path / "approval_logs"
    monkeypatch.setattr(queue, "_log_dir", log_dir)
    monkeypatch.setattr(queue, "_pending_path", log_dir / "pending.json")

    first_id = queue.submit({"file_path": "a.txt", "action_type": "edit", "reason": "first"})
    assert queue.resolve(first_id, True)

    second_id = queue.submit({"file_path": "b.txt", "action_type": "edit", "reason": "second"})
    assert queue.resolve(second_id, False)

    assert second_id != first_id
    resolved = sorted(log_dir.glob("resolved_*.json"))
    assert len(resolved) == 2
    reasons = {
        json.loads(path.read_text(encoding="utf-8"))["spec"]["reason"]
        for path in resolved
    }
    assert reasons == {"first", "second"}
