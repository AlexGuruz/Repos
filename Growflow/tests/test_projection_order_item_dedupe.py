from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "build_projection_dedupe",
    REPO / "scripts" / "build_projection_by_category_brand.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _order_line() -> dict:
    return {
        "objectId": "order-line-1",
        "SoldAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "GrossPrice": 2000,
        "COG": 1000,
        "Product": {
            "objectId": "product-1",
            "Name": "Test Flower",
            "Brand": {"Name": "Test Brand"},
        },
        "ProductCategory": {"Name": "Flower"},
    }


def test_projection_main_dedupes_duplicate_order_items(monkeypatch, tmp_path: Path) -> None:
    out = tmp_path / "projection.md"
    duplicate = _order_line()

    monkeypatch.setattr(_mod, "_fetch_chunk", lambda **_kwargs: ([duplicate, dict(duplicate)], _mod.ORDER_ITEMS_QUERY))
    monkeypatch.setattr(_mod, "validate_and_normalize", lambda **_kwargs: {"ok": True, "report_path": "test"})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_projection_by_category_brand.py",
            "--days",
            "1",
            "--velocity-days",
            "1",
            "--allocation-mode",
            "gross-share",
            "--pool",
            "100",
            "--out",
            str(out),
            "--no-layer2",
            "--landed-cog",
            "off",
            "--exclude-brands",
            "",
            "--validation-mode",
            "warning",
        ],
    )

    assert _mod.main() == 0
    text = out.read_text(encoding="utf-8")
    assert "**Unique order lines counted:** 1" in text
