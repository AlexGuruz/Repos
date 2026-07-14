from __future__ import annotations

import json
from zoneinfo import ZoneInfo

from scripts import register_close_taxes_sheet as taxes


def test_poll_preserves_cursor_when_export_fails(tmp_path, monkeypatch) -> None:
    state_path = tmp_path / "state" / "register_close_taxes_state.json"
    state_path.parent.mkdir(parents=True)
    old_cursor = "2026-06-02T03:00:00.000Z"
    state_path.write_text(
        json.dumps(
            {
                "last_poll_at": old_cursor,
                "notified_shift_ids": [],
                "notified_sales_dates": {},
            }
        ),
        encoding="utf-8",
    )
    txs = [
        {
            "Register": {"objectId": "r1", "Name": "Register 1"},
            "Shift": {
                "objectId": "shift1",
                "IsOpen": False,
                "EndTime": {"iso": "2026-06-02T03:04:29.641Z"},
                "StartTime": {"iso": "2026-06-01T12:55:40.319Z"},
                "Register": {"objectId": "r1", "Name": "Register 1"},
            },
        }
    ]

    monkeypatch.setattr(taxes, "fetch_transactions_since", lambda *a, **k: txs)

    def _fail_export(*args, **kwargs) -> None:
        raise RuntimeError("sheet unavailable")

    monkeypatch.setattr(taxes, "_export_for_date", _fail_export)
    monkeypatch.setattr(taxes, "_append_log", lambda *a, **k: None)

    exported = taxes._poll_once(
        {
            "state_path": str(state_path),
            "register_name": "Register 1",
            "notify_once_per_sales_date": True,
        },
        ZoneInfo("America/Chicago"),
        dry_run=False,
        lookback_hours=36,
    )

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert exported == 0
    assert saved["last_poll_at"] == old_cursor
    assert saved["notified_shift_ids"] == []
    assert saved["notified_sales_dates"] == {}
