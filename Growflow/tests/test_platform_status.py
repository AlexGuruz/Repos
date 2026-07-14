"""Platform freshness / fixture detector unit tests."""
from __future__ import annotations

from lib.platform_config import GrowflowPlatformConfig
from lib.platform_status import enrich_retail_payload, is_fixture_dashboard


def test_fixture_detector_flags_sample_day():
    meta = {"order_count": 1, "store_net_sales": 9.0}
    assert is_fixture_dashboard(meta) is True


def test_fixture_detector_allows_real_volume():
    meta = {"order_count": 120, "store_net_sales": 8500.0}
    assert is_fixture_dashboard(meta) is False


def test_enrich_marks_unhealthy_for_fixture():
    cfg = GrowflowPlatformConfig()
    payload = {
        "meta": {
            "order_count": 1,
            "store_net_sales": 9.0,
            "built_at": "2026-06-15T17:58:07Z",
            "validation": {"ok": True},
        }
    }
    out = enrich_retail_payload(payload, cfg=cfg)
    trust = out["meta"]["trust"]
    assert trust["fixture_suspected"] is True
    assert trust["healthy"] is False
    assert trust["freshness"] == "degraded"
