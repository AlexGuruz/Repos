from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo


REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "build_projection",
    REPO / "scripts" / "build_projection_by_category_brand.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def test_projection_accepts_each_order_item_key_once() -> None:
    tz = ZoneInfo("America/Chicago")
    seen: set[str] = set()
    line = {"objectId": "order-line-1", "SoldAt": "2026-06-01T15:00:00.000Z"}

    first = _mod._unique_order_item_local_date(
        line,
        seen=seen,
        tz=tz,
        report_start_local=date(2026, 6, 1),
        report_end_local=date(2026, 6, 1),
    )
    duplicate = _mod._unique_order_item_local_date(
        dict(line),
        seen=seen,
        tz=tz,
        report_start_local=date(2026, 6, 1),
        report_end_local=date(2026, 6, 1),
    )

    assert first == date(2026, 6, 1)
    assert duplicate is None
    assert seen == {"objectId:order-line-1"}
