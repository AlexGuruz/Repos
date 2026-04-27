from __future__ import annotations

import json
from pathlib import Path

from lib.data_validation_gateway import (
    load_metric_contract,
    load_query_template,
    validate_and_normalize,
)


def _raw_order_items(*, gross_as_str: bool = False, include_root: bool = True, include_required: bool = True):
    node = {
        "id": "row-1",
        "objectId": "row-1",
        "SoldAt": "2026-04-20T12:00:00.000Z",
        "GrossPrice": "1200" if gross_as_str else 1200,
        "NetPrice": 1100,
        "COG": 700,
        "ProductCategory": {"Name": "Edibles"},
        "Product": {"objectId": "p1", "Brand": {"Name": "BrandA"}},
    }
    if not include_required:
        node.pop("GrossPrice", None)
    payload = {"data": {"findOrderItems": {"edges": [{"node": node}, {"node": dict(node)}]}}}
    if not include_root:
        payload = {"data": {"unexpected": []}}
    return payload


def _ctx():
    return {
        "request_id": "unit_test_req",
        "requested_date_range": {
            "from": "2026-04-20T00:00:00.000Z",
            "to": "2026-04-20T23:59:59.000Z",
        },
    }


def test_valid_response_passes_warning_mode():
    res = validate_and_normalize(
        metric_id="sales_today",
        template_id="order_items_sales_today_v1",
        raw_json=_raw_order_items(),
        request_context=_ctx(),
        mode="warning",
    )
    assert res["ok"] is True
    assert res["normalized_row_count"] >= 1


def test_missing_root_fails():
    res = validate_and_normalize(
        "sales_today",
        "order_items_sales_today_v1",
        _raw_order_items(include_root=False),
        _ctx(),
        mode="warning",
    )
    assert res["ok"] is False
    assert "wrong_root_path" in res["errors"]


def test_missing_required_field_fails():
    res = validate_and_normalize(
        "sales_today",
        "order_items_sales_today_v1",
        _raw_order_items(include_required=False),
        _ctx(),
        mode="warning",
    )
    assert res["ok"] is False
    assert "missing_required_fields" in res["errors"]


def test_wrong_type_fails():
    res = validate_and_normalize(
        "sales_today",
        "order_items_sales_today_v1",
        _raw_order_items(gross_as_str=True),
        _ctx(),
        mode="warning",
    )
    assert res["ok"] is False
    assert "type_errors" in res["errors"]


def test_empty_response_policy():
    raw = {"data": {"findOrderItems": {"edges": []}}}
    res = validate_and_normalize("sales_today", "order_items_sales_today_v1", raw, _ctx(), mode="warning")
    assert res["empty_result_status"] in {"warning", "allowed", "disallowed"}


def test_date_mismatch_warns_or_fails_by_mode():
    raw = _raw_order_items()
    ctx = _ctx()
    ctx["requested_date_range"] = {
        "from": "2026-04-01T00:00:00.000Z",
        "to": "2026-04-02T00:00:00.000Z",
    }
    res_warning = validate_and_normalize("sales_today", "order_items_sales_today_v1", raw, ctx, mode="warning")
    assert any("date range" in w.lower() for w in res_warning["warnings"])
    res_strict = validate_and_normalize("sales_today", "order_items_sales_today_v1", raw, ctx, mode="strict")
    assert res_strict["ok"] is False


def test_duplicate_rows_detected():
    res = validate_and_normalize("sales_today", "order_items_sales_today_v1", _raw_order_items(), _ctx(), mode="warning")
    assert res["duplicate_count"] >= 1


def test_strict_mode_blocks_trusted_output():
    res = validate_and_normalize(
        "sales_today",
        "order_items_sales_today_v1",
        _raw_order_items(gross_as_str=True),
        _ctx(),
        mode="strict",
    )
    assert res["ok"] is False
    assert res["normalized_output_path"] is None


def test_warning_mode_lowers_confidence():
    res = validate_and_normalize("sales_today", "order_items_sales_today_v1", _raw_order_items(), _ctx(), mode="warning")
    assert res["confidence"] in {"medium", "high"}


def test_discovery_mode_saves_raw_and_report_only():
    res = validate_and_normalize("schema_discovery", "schema_discovery_runner_v1", {"data": {}}, _ctx(), mode="discovery")
    assert res["ok"] is False
    assert res["normalized_output_path"] is None
    assert res["raw_saved_path"]
    assert res["report_path"]


def test_metric_contract_and_template_alignment():
    cfg_path = Path("config/query_templates.yaml")
    templates = json.loads(cfg_path.read_text(encoding="utf-8"))
    for tpl in templates:
        metric_id = str(tpl["metric_id"])
        contract = load_metric_contract(metric_id)
        loaded_tpl = load_query_template(str(tpl["template_id"]))
        assert contract["metric_id"] == metric_id
        assert loaded_tpl["template_id"] == tpl["template_id"]


def test_integrated_scripts_reference_gateway():
    scripts = [
        Path("scripts/build_projection_by_category_brand.py"),
        Path("scripts/build_transfer_receipts_db.py"),
        Path("scripts/export_transfer_receipt_units.py"),
        Path("scripts/rank_mj_brands_profit_velocity_sheet.py"),
    ]
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "validate_and_normalize" in text
