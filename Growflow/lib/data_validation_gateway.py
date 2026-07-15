"""
Growflow data validation gateway.

Implements contract/template-based validation for metric responses before scripts
treat outputs as trusted.
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.brand_category_normalize import apply_to_rows as apply_brand_category_rows
from lib.schema_verification import verify_against_baseline


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_DIR = REPO_ROOT / "contracts"
QUERY_TEMPLATES_PATH = REPO_ROOT / "config" / "query_templates.yaml"
RAW_RESPONSES_DIR = REPO_ROOT / "state" / "raw_responses"
TRUSTED_OUTPUTS_DIR = REPO_ROOT / "state" / "trusted_outputs"
VALIDATION_REPORTS_DIR = REPO_ROOT / "state" / "validation_reports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _read_json(path: Path) -> dict[str, Any]:
    return _as_dict(json.loads(path.read_text(encoding="utf-8")))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _coerce_request_id(request_context: dict[str, Any] | None) -> str:
    ctx = _as_dict(request_context)
    request_id = str(ctx.get("request_id") or "").strip()
    return request_id or f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _extract_path(payload: Any, path: str) -> Any:
    """Dot-path lookup with GraphQL list/union tolerance.

    When a path segment lands on a list (e.g. OrderItems.Orders [... on Orders]),
    take the first dict element that contains the next key. Matches live GrowFlow
    shapes and lib.retail_dashboard.normalize.first_order_fragment.
    """
    cur: Any = payload
    for part in [p for p in str(path).split(".") if p]:
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
            continue
        if isinstance(cur, list):
            nxt: Any = None
            for item in cur:
                if isinstance(item, dict) and part in item and item[part] is not None:
                    nxt = item[part]
                    break
            if nxt is None:
                for item in cur:
                    if isinstance(item, dict) and part in item:
                        nxt = item[part]
                        break
            if nxt is None and not any(isinstance(item, dict) and part in item for item in cur):
                return None
            cur = nxt
            continue
        return None
    return cur


def _looks_like_iso(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return ("T" in text and ("Z" in text or "+" in text)) or (len(text) == 10 and text.count("-") == 2)


def _to_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _infer_type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return type(value).__name__


def _type_matches(expected: str, value: Any) -> bool:
    name = expected.strip().lower()
    if name in {"str", "string"}:
        return isinstance(value, str)
    if name in {"int", "integer"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if name in {"float", "number"}:
        return (isinstance(value, (int, float)) and not isinstance(value, bool))
    if name in {"bool", "boolean"}:
        return isinstance(value, bool)
    if name in {"dict", "object"}:
        return isinstance(value, dict)
    if name in {"list", "array"}:
        return isinstance(value, list)
    if name in {"iso_datetime", "datetime"}:
        return _to_datetime(value) is not None
    if name in {"iso_date", "date"}:
        if not isinstance(value, str):
            return False
        txt = value.strip()
        return len(txt) == 10 and txt.count("-") == 2
    return True


def _field_confidence_counts(contract: dict[str, Any]) -> dict[str, int]:
    fc = _as_dict(contract.get("field_confidence"))
    out = {"confirmed": 0, "inferred": 0, "unstable": 0}
    for tier in fc.values():
        t = str(tier).strip().lower()
        if t in out:
            out[t] += 1
    return out


def _confidence_score_from_contract(
    contract: dict[str, Any],
    *,
    drift_block: dict[str, Any] | None,
    schema_drift_warnings: list[str],
) -> float:
    """Numeric 0..1 trust score from field annotations and schema drift."""
    fc = _as_dict(contract.get("field_confidence"))
    weights = {"confirmed": 1.0, "inferred": 0.88, "unstable": 0.72}
    if fc:
        vals = [weights.get(str(v).strip().lower(), 0.85) for v in fc.values()]
        base = sum(vals) / max(1, len(vals))
    else:
        base = 0.9
    if drift_block and drift_block.get("drift"):
        d = drift_block["drift"]
        if d.get("critical_missing_paths"):
            base *= 0.72
        elif d.get("missing_paths"):
            base *= 0.94
        if d.get("possibly_unstable_new_paths"):
            base *= 0.97
    if schema_drift_warnings:
        base *= max(0.5, 1.0 - 0.02 * min(5, len(schema_drift_warnings)))
    return max(0.0, min(1.0, round(float(base), 4)))


def _confidence_label_from_score(score: float, mode: str, has_errors: bool, gate_warnings: int) -> str:
    if mode == "discovery":
        return "discovery"
    if has_errors or score <= 0.0:
        return "low"
    if mode == "strict" and gate_warnings > 0:
        return "low"
    if mode == "warning" and gate_warnings > 0 and score < 0.82:
        return "low"
    if score >= 0.9 and gate_warnings == 0:
        return "high"
    if score >= 0.75:
        return "medium"
    return "low"


def _load_templates_registry() -> list[dict[str, Any]]:
    # YAML is a superset of JSON. Keep this file JSON-compatible for stdlib parsing.
    if not QUERY_TEMPLATES_PATH.is_file():
        return []
    text = QUERY_TEMPLATES_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"query_templates.yaml must be JSON-compatible YAML: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError("query_templates.yaml must contain a list of template entries")
    return [_as_dict(item) for item in payload]


def load_metric_contract(metric_id: str) -> dict[str, Any]:
    path = CONTRACTS_DIR / f"{metric_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Metric contract not found: {path}")
    contract = _read_json(path)
    if str(contract.get("metric_id") or "") != metric_id:
        raise ValueError(f"Contract metric_id mismatch in {path}")
    return contract


def load_query_template(template_id: str) -> dict[str, Any]:
    templates = _load_templates_registry()
    for template in templates:
        if str(template.get("template_id") or "") == template_id:
            return template
    raise KeyError(f"Query template not found: {template_id}")


def _build_rows_for_validation(metric_id: str, root_payload: Any) -> list[dict[str, Any]]:
    # Default path: GraphQL connections with edges/node shape.
    if isinstance(root_payload, dict):
        edges = root_payload.get("edges")
        if isinstance(edges, list):
            out: list[dict[str, Any]] = []
            for edge in edges:
                node = _as_dict(edge).get("node")
                if isinstance(node, dict):
                    out.append(node)
            return out
    if isinstance(root_payload, list):
        return [r for r in root_payload if isinstance(r, dict)]
    if metric_id in {"transfer_receipts", "transfer_units"} and isinstance(root_payload, dict):
        nodes = root_payload.get("nodes")
        if isinstance(nodes, list):
            return [n for n in nodes if isinstance(n, dict)]
    return []


def validate_raw_response(
    metric_id: str,
    template_id: str,
    raw_json: dict[str, Any],
    request_context: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = load_metric_contract(metric_id)
    template = load_query_template(template_id)
    context = _as_dict(request_context)
    required_missing: list[str] = []
    type_errors: list[dict[str, str]] = []
    parser_warnings: list[str] = []

    expected_root = str(contract.get("expected_root_path") or template.get("expected_response_root") or "")
    root_payload = _extract_path(raw_json, expected_root) if expected_root else None
    expected_root_found = root_payload is not None

    if not expected_root_found:
        parser_warnings.append(f"Expected root path not found: {expected_root}")
        rows: list[dict[str, Any]] = []
    else:
        rows = _build_rows_for_validation(metric_id, root_payload)

    required_fields = [str(x) for x in _as_list(contract.get("required_fields"))]
    optional_fields = [str(x) for x in _as_list(contract.get("optional_fields"))]
    field_types = _as_dict(contract.get("field_types"))

    for row_idx, row in enumerate(rows):
        for field in required_fields:
            value = _extract_path(row, field)
            if value is None:
                required_missing.append(f"row[{row_idx}].{field}")
        for field, expected_type in field_types.items():
            value = _extract_path(row, str(field))
            if value is None:
                continue
            if not _type_matches(str(expected_type), value):
                type_errors.append(
                    {
                        "field": str(field),
                        "expected": str(expected_type),
                        "actual": _infer_type_name(value),
                        "row_index": str(row_idx),
                    }
                )

    empty_policy = str(contract.get("empty_result_policy") or "warn")
    empty_result = len(rows) == 0
    empty_result_status = "ok"
    if empty_result:
        if empty_policy in {"allow", "allowed"}:
            empty_result_status = "allowed"
        elif empty_policy in {"warn", "warning"}:
            empty_result_status = "warning"
        else:
            empty_result_status = "disallowed"

    return {
        "metric_id": metric_id,
        "template_id": template_id,
        "request_id": _coerce_request_id(context),
        "requested_date_range": _as_dict(context.get("requested_date_range")),
        "expected_root": expected_root,
        "expected_root_found": expected_root_found,
        "required_fields": required_fields,
        "optional_fields": optional_fields,
        "rows": rows,
        "root_payload": root_payload,
        "missing_required_fields": required_missing,
        "type_errors": type_errors,
        "empty_result_status": empty_result_status,
        "parser_warnings": parser_warnings,
    }


def validate_target_alignment(
    metric_id: str,
    raw_json: dict[str, Any],
    request_context: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = load_metric_contract(metric_id)
    context = _as_dict(request_context)
    template_id = str(context.get("template_id") or contract.get("allowed_query_template_ids", [""])[0])
    raw_validation = validate_raw_response(metric_id, template_id, raw_json, context)
    rows = _as_list(raw_validation.get("rows"))
    requested = _as_dict(context.get("requested_date_range"))
    req_start = _to_datetime(requested.get("from"))
    req_end = _to_datetime(requested.get("to"))

    date_candidates: list[datetime] = []
    date_fields = [str(x) for x in _as_list(contract.get("date_field_expectations", {}).get("date_fields"))]
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in date_fields:
            dt = _to_datetime(_extract_path(row, field))
            if dt is not None:
                date_candidates.append(dt)

    warnings: list[str] = []
    response_range: dict[str, str | None] = {"from": None, "to": None}
    if date_candidates:
        low = min(date_candidates)
        high = max(date_candidates)
        response_range = {
            "from": low.isoformat().replace("+00:00", "Z"),
            "to": high.isoformat().replace("+00:00", "Z"),
        }
        if req_start and low < req_start:
            warnings.append("Response contains rows earlier than requested date range.")
        if req_end and high > req_end:
            warnings.append("Response contains rows later than requested date range.")
    elif date_fields:
        warnings.append("No parseable date field values found for alignment check.")

    return {
        "response_date_range_detected": response_range,
        "target_alignment_warnings": warnings,
    }


def normalize_metric_output(
    metric_id: str,
    raw_json: dict[str, Any],
    request_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    contract = load_metric_contract(metric_id)
    context = _as_dict(request_context)
    template_id = str(context.get("template_id") or contract.get("allowed_query_template_ids", [""])[0])
    validated = validate_raw_response(metric_id, template_id, raw_json, context)
    rows = _as_list(validated.get("rows"))
    normalized: list[dict[str, Any]] = []

    if metric_id == "sales_today":
        for row in rows:
            normalized.append(
                {
                    "order_item_id": row.get("objectId") or row.get("id"),
                    "sold_at": row.get("SoldAt"),
                    "gross_price_cents": row.get("GrossPrice"),
                    "net_price_cents": row.get("NetPrice"),
                }
            )
        return normalized

    if metric_id in {"sales_by_brand_category", "brand_profit_velocity", "projection_by_category_brand"}:
        for row in rows:
            prod = _as_dict(row.get("Product"))
            brand = _as_dict(prod.get("Brand")).get("Name")
            cat = _as_dict(row.get("ProductCategory")).get("Name")
            normalized.append(
                {
                    "order_item_id": row.get("objectId") or row.get("id"),
                    "brand_name": brand,
                    "category_name": cat,
                    "sold_at": row.get("SoldAt"),
                    "gross_price_cents": row.get("GrossPrice"),
                    "cog_cents": row.get("COG"),
                    "product_object_id": prod.get("objectId"),
                }
            )
        return normalized

    if metric_id == "inventory_on_hand":
        for row in rows:
            prod = _as_dict(row.get("Product"))
            normalized.append(
                {
                    "package_object_id": row.get("objectId") or row.get("id"),
                    "created_at": row.get("createdAt"),
                    "current_qty": row.get("CurrentQty"),
                    "original_qty": row.get("OriginalQty"),
                    "cost_cents": row.get("Cost"),
                    "brand_name": _as_dict(prod.get("Brand")).get("Name"),
                    "category_name": _as_dict(prod.get("ProductCategory")).get("Name"),
                }
            )
        return normalized

    if metric_id in {"transfer_receipts", "transfer_units"}:
        for row in rows:
            pkg = _as_dict(row)
            prod = _as_dict(pkg.get("Product"))
            normalized.append(
                {
                    "transfer_object_id": row.get("objectId"),
                    "status": row.get("Status"),
                    "received_at": row.get("ReceivedAt"),
                    "from_name": row.get("FromName"),
                    "package_object_id": pkg.get("objectId"),
                    "product_object_id": prod.get("objectId"),
                    "original_qty": pkg.get("OriginalQty"),
                    "current_qty": pkg.get("CurrentQty"),
                    "cost_cents": pkg.get("Cost"),
                }
            )
        return normalized

    if metric_id == "schema_discovery":
        for row in rows:
            normalized.append(deepcopy(row))
        return normalized

    for row in rows:
        normalized.append(deepcopy(row))
    return normalized


def run_sanity_checks(
    metric_id: str,
    normalized_rows: list[dict[str, Any]],
    request_context: dict[str, Any] | None,
) -> dict[str, Any]:
    contract = load_metric_contract(metric_id)
    duplicate_policy = str(contract.get("duplicate_policy") or "warn")
    sanity_warnings: list[str] = []
    seen: set[str] = set()
    duplicate_count = 0
    dedupe_key_fields = [str(x) for x in _as_list(contract.get("sanity_checks", {}).get("dedupe_key_fields"))]

    for row in normalized_rows:
        parts: list[str] = []
        for field in dedupe_key_fields:
            parts.append(str(_extract_path(row, field)))
        key = "|".join(parts) if parts else json.dumps(row, sort_keys=True, default=str)
        if key in seen:
            duplicate_count += 1
        else:
            seen.add(key)

    if duplicate_count > 0 and duplicate_policy in {"fail", "error"}:
        sanity_warnings.append(f"Detected {duplicate_count} duplicate row(s); duplicate policy=fail.")
    elif duplicate_count > 0:
        sanity_warnings.append(f"Detected {duplicate_count} duplicate row(s).")

    gross_field = str(contract.get("sanity_checks", {}).get("non_negative_field", ""))
    if gross_field:
        negatives = 0
        for row in normalized_rows:
            value = _extract_path(row, gross_field)
            if isinstance(value, (int, float)) and value < 0:
                negatives += 1
        if negatives > 0:
            sanity_warnings.append(f"Detected {negatives} negative values for field '{gross_field}'.")

    return {"duplicate_count": duplicate_count, "sanity_warnings": sanity_warnings}


def write_validation_report(
    metric_id: str,
    template_id: str,
    request_id: str,
    report: dict[str, Any],
) -> Path:
    metric_dir = VALIDATION_REPORTS_DIR / metric_id
    metric_dir.mkdir(parents=True, exist_ok=True)
    report_payload = deepcopy(report)
    report_payload["metric_id"] = metric_id
    report_payload["template_id"] = template_id
    report_payload["request_id"] = request_id
    report_payload["generated_at"] = _now_iso()
    return _write_json(metric_dir / f"{request_id}.json", report_payload)


def validate_and_normalize(
    metric_id: str,
    template_id: str,
    raw_json: dict[str, Any],
    request_context: dict[str, Any] | None,
    mode: str = "strict",
) -> dict[str, Any]:
    if mode not in {"strict", "warning", "discovery"}:
        raise ValueError("mode must be one of: strict, warning, discovery")

    context = _as_dict(request_context)
    request_id = _coerce_request_id(context)
    context["request_id"] = request_id
    context["template_id"] = template_id

    raw_path = _write_json(RAW_RESPONSES_DIR / metric_id / f"{request_id}.json", _as_dict(raw_json))
    raw_validation = validate_raw_response(metric_id, template_id, raw_json, context)
    contract = load_metric_contract(metric_id)
    raw_rows = _as_list(raw_validation.get("rows"))
    drift_block = verify_against_baseline(
        metric_id,
        raw_rows,
        required_fields=_as_list(contract.get("required_fields")),
        optional_fields=_as_list(contract.get("optional_fields")),
        update_baseline=bool(context.get("update_schema_baseline", False)),
    )
    schema_drift_warnings = _as_list(drift_block.get("schema_drift_warnings"))

    alignment = validate_target_alignment(metric_id, raw_json, context)
    normalized_rows = normalize_metric_output(metric_id, raw_json, context)
    normalized_rows = apply_brand_category_rows(normalized_rows)
    sanity = run_sanity_checks(metric_id, normalized_rows, context)

    missing_required_fields = _as_list(raw_validation.get("missing_required_fields"))
    type_errors = _as_list(raw_validation.get("type_errors"))
    parser_warnings = _as_list(raw_validation.get("parser_warnings"))
    target_warnings = _as_list(alignment.get("target_alignment_warnings"))
    sanity_warnings = _as_list(sanity.get("sanity_warnings"))
    expected_root_found = bool(raw_validation.get("expected_root_found"))
    empty_result_status = str(raw_validation.get("empty_result_status") or "warning")

    hard_failures: list[str] = []
    if not expected_root_found:
        hard_failures.append("wrong_root_path")
    if missing_required_fields:
        hard_failures.append("missing_required_fields")
    if type_errors:
        hard_failures.append("type_errors")
    if empty_result_status == "disallowed":
        hard_failures.append("empty_result_disallowed")
    if context.get("fail_on_schema_drift") and drift_block.get("drift"):
        d = drift_block.get("drift") or {}
        if d.get("critical_missing_paths"):
            hard_failures.append("schema_drift_critical")

    has_errors = len(hard_failures) > 0
    gate_warnings = parser_warnings + target_warnings + sanity_warnings
    warning_count_gate = len(gate_warnings)

    if mode == "strict":
        ok = not has_errors and warning_count_gate == 0
    elif mode == "warning":
        ok = not has_errors
    else:
        ok = False

    confidence_score = _confidence_score_from_contract(
        contract,
        drift_block=drift_block if drift_block.get("baseline_exists") else None,
        schema_drift_warnings=schema_drift_warnings,
    )
    if has_errors:
        confidence_score = 0.0
    elif mode == "discovery":
        confidence_score = min(confidence_score, 0.35)

    confidence = _confidence_label_from_score(
        confidence_score,
        mode,
        has_errors,
        warning_count_gate,
    )
    fc_summary = _field_confidence_counts(contract)

    normalized_output_path: Path | None = None
    if mode != "discovery" and ok:
        normalized_output_path = _write_json(
            TRUSTED_OUTPUTS_DIR / metric_id / f"{request_id}.json",
            {
                "metric_id": metric_id,
                "template_id": template_id,
                "request_id": request_id,
                "mode": mode,
                "generated_at": _now_iso(),
                "confidence_score": confidence_score,
                "confidence_label": confidence,
                "field_confidence": contract.get("field_confidence") or {},
                "field_confidence_counts": fc_summary,
                "schema_drift": drift_block,
                "rows": normalized_rows,
            },
        )

    report = {
        "ok": ok,
        "metric_id": metric_id,
        "template_id": template_id,
        "request_id": request_id,
        "mode": mode,
        "requested_date_range": raw_validation.get("requested_date_range"),
        "response_date_range_detected": alignment.get("response_date_range_detected"),
        "expected_root_found": expected_root_found,
        "missing_required_fields": missing_required_fields,
        "type_errors": type_errors,
        "empty_result_status": empty_result_status,
        "duplicate_count": sanity.get("duplicate_count"),
        "sanity_warnings": sanity_warnings,
        "target_alignment_warnings": target_warnings,
        "parser_warnings": parser_warnings,
        "schema_drift_warnings": schema_drift_warnings,
        "schema_verification": drift_block,
        "normalized_row_count": len(normalized_rows),
        "confidence": confidence,
        "confidence_score": confidence_score,
        "field_confidence": contract.get("field_confidence") or {},
        "field_confidence_counts": fc_summary,
        "hard_failures": hard_failures,
        "raw_saved_path": str(raw_path),
        "normalized_output_path": str(normalized_output_path) if normalized_output_path else None,
    }
    report_path = write_validation_report(metric_id, template_id, request_id, report)
    report["report_path"] = str(report_path)

    return {
        **report,
        "normalized_rows": normalized_rows,
        "errors": hard_failures,
        "warnings": gate_warnings + schema_drift_warnings,
    }
