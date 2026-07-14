"""
Reconcile promoted Retail Dashboard Operations metrics against a trusted reference.

Compares ``retail_dashboard_latest.json`` (computed) to CSV/JSON exports from
native GrowFlow or manual reports. No GraphQL at request time.
"""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DASHBOARD_JSON = REPO_ROOT / "data" / "retail_dashboard_latest.json"
DEFAULT_REPORT_JSON = REPO_ROOT / "data" / "retail_reconciliation_latest.json"
DEFAULT_CONFIG = REPO_ROOT / "config" / "retail_dashboard.yaml"

CSV_REQUIRED_COLUMNS = frozenset({"section", "key", "metric", "value"})
CheckStatus = Literal["pass", "fail", "warning"]


@dataclass
class Tolerance:
    money_abs: float = 1.0
    pct: float = 0.005


@dataclass
class ReconcileConfig:
    dashboard_path: Path
    reference_type: str | None  # csv | json | None
    reference_path: Path | None
    out_path: Path
    tolerance: Tolerance


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def load_retail_dashboard_config(path: Path | None = None) -> dict[str, Any]:
    p = path or DEFAULT_CONFIG
    out: dict[str, Any] = {
        "reconciliation": {
            "money_tolerance_abs": 1.0,
            "pct_tolerance": 0.005,
            "default_out": "data/retail_reconciliation_latest.json",
            "default_dashboard_json": "data/retail_dashboard_latest.json",
        }
    }
    if not p.is_file():
        return out
    text = p.read_text(encoding="utf-8")
    block = re.search(r"^\s*reconciliation:\s*\n((?:[ \t]+[^\n]+\n?)*)", text, re.MULTILINE)
    if not block:
        return out
    rec = block.group(1)
    for key, cast in (
        ("money_tolerance_abs", float),
        ("pct_tolerance", float),
    ):
        raw = _yaml_scalar(rec, key)
        if raw is not None:
            out["reconciliation"][key] = cast(raw)
    for key in ("default_out", "default_dashboard_json", "default_reference_csv", "default_reference_json"):
        raw = _yaml_scalar(rec, key)
        if raw is not None:
            out["reconciliation"][key] = raw
    raw_req = _yaml_scalar(rec, "require_reference")
    if raw_req is not None:
        out["reconciliation"]["require_reference"] = raw_req.lower() in ("1", "true", "yes")
    return out


def load_dashboard_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"dashboard json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("dashboard json root must be an object")
    if "meta" not in data:
        raise ValueError("dashboard json missing meta block")
    return data


def _parse_float(raw: Any) -> float:
    if raw is None or raw == "":
        raise ValueError("empty numeric value")
    return round(float(raw), 2)


def load_reference_csv(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"reference csv not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("reference csv has no header row")
        cols = {c.strip().lower() for c in reader.fieldnames if c}
        missing = CSV_REQUIRED_COLUMNS - cols
        if missing:
            raise ValueError(f"reference csv missing required columns: {sorted(missing)}")

        ref: dict[str, Any] = {
            "period": {},
            "store": {},
            "budtender_sales": {},
            "discounts_over_time": {},
            "brand_summary": {},
            "budtender_by_category": {},
        }
        for row in reader:
            section = str(row.get("section") or "").strip().lower()
            key = str(row.get("key") or "").strip()
            metric = str(row.get("metric") or "").strip().lower()
            if section == "period":
                raw_val = str(row.get("value") or "").strip()
                if metric == "start":
                    ref.setdefault("period", {})["start"] = key or raw_val
                elif metric == "end":
                    ref.setdefault("period", {})["end"] = key or raw_val
                continue
            value = _parse_float(row.get("value"))
            if section == "store":
                ref["store"][metric] = value
            elif section == "budtender":
                ref["budtender_sales"].setdefault(key, {})[metric] = value
            elif section == "daily":
                ref["discounts_over_time"].setdefault(key, {})[metric] = value
            elif section == "brand":
                ref["brand_summary"].setdefault(key, {})[metric] = value
            elif section in ("category_budtender", "category-budtender", "cat_bt"):
                ref["budtender_by_category"].setdefault(key, {})[metric] = value
            else:
                raise ValueError(f"unknown reference csv section: {section}")
    return ref


def load_reference_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"reference json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("reference json root must be an object")
    return _normalize_reference_json(data)


def _normalize_reference_json(data: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "period": data.get("period") or {},
        "store": {},
        "budtender_sales": {},
        "discounts_over_time": {},
        "brand_summary": {},
        "budtender_by_category": {},
    }
    store = data.get("store") or {}
    if isinstance(store, dict):
        if "net_sales" in store:
            ref["store"]["net_sales"] = _parse_float(store["net_sales"])
        for k, v in store.items():
            if k != "net_sales":
                ref["store"][k] = _parse_float(v) if isinstance(v, (int, float, str)) else v
    meta = data.get("meta") or {}
    if not ref["store"].get("net_sales") and meta.get("store_net_sales") is not None:
        ref["store"]["net_sales"] = _parse_float(meta["store_net_sales"])
    if not ref["period"] and meta.get("period"):
        ref["period"] = meta["period"]

    for row in data.get("budtender_sales") or []:
        name = str(row.get("budtender") or row.get("name") or "")
        if name:
            ref["budtender_sales"][name] = {"net_sales": _parse_float(row.get("net_sales"))}

    for row in data.get("discounts_over_time") or []:
        d = str(row.get("date") or "")
        if d:
            ref["discounts_over_time"][d] = {"net_sales": _parse_float(row.get("net_sales"))}

    for row in data.get("brand_summary") or []:
        key = str(row.get("canonical_brand") or row.get("brand_name") or row.get("brand") or "")
        if key:
            ref["brand_summary"][key] = {"net_sales": _parse_float(row.get("net_sales"))}

    for row in data.get("budtender_by_category") or []:
        cat = str(row.get("category_name") or row.get("category") or "")
        bt = str(row.get("budtender") or "")
        if cat and bt:
            ref["budtender_by_category"][f"{cat}|{bt}"] = {
                "net_sales": _parse_float(row.get("net_sales")),
            }
    return ref


def _delta(expected: float, actual: float) -> tuple[float, float]:
    delta_abs = round(actual - expected, 2)
    if expected:
        delta_pct = round(delta_abs / expected, 6)
    else:
        delta_pct = 0.0 if delta_abs == 0 else float("inf")
    return delta_abs, delta_pct


def within_tolerance(expected: float, actual: float, tol: Tolerance) -> bool:
    delta_abs, delta_pct = _delta(expected, actual)
    if abs(delta_abs) <= tol.money_abs:
        return True
    if expected and abs(delta_pct) <= tol.pct:
        return True
    return False


def _make_check(
    *,
    name: str,
    expected: float,
    actual: float,
    tol: Tolerance,
    blocking: bool = True,
) -> dict[str, Any]:
    delta_abs, delta_pct = _delta(expected, actual)
    ok = within_tolerance(expected, actual, tol)
    status: CheckStatus = "pass" if ok else ("fail" if blocking else "warning")
    return {
        "name": name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "delta_abs": delta_abs,
        "delta_pct": delta_pct,
        "tolerance": tol.money_abs,
        "tolerance_pct": tol.pct,
        "blocking": blocking,
    }


def _extract_actual(dashboard: dict[str, Any]) -> dict[str, Any]:
    meta = dashboard.get("meta") or {}
    actual: dict[str, Any] = {
        "period": meta.get("period"),
        "store_net_sales": _parse_float(meta.get("store_net_sales") or 0),
        "budtender_sales": {
            str(r.get("budtender")): _parse_float(r.get("net_sales"))
            for r in dashboard.get("budtender_sales") or []
            if r.get("budtender") is not None
        },
        "discounts_over_time": {
            str(r.get("date")): _parse_float(r.get("net_sales"))
            for r in dashboard.get("discounts_over_time") or []
            if r.get("date")
        },
        "brand_summary": {
            str(r.get("canonical_brand") or r.get("brand_name")): _parse_float(r.get("net_sales"))
            for r in dashboard.get("brand_summary") or []
            if r.get("canonical_brand") or r.get("brand_name")
        },
        "budtender_by_category": {
            f"{r.get('category_name')}|{r.get('budtender')}": _parse_float(r.get("net_sales"))
            for r in dashboard.get("budtender_by_category") or []
            if r.get("category_name") and r.get("budtender")
        },
    }
    return actual


def run_sum_gate_checks(actual: dict[str, Any], tol: Tolerance) -> list[dict[str, Any]]:
    store = actual["store_net_sales"]
    checks = [
        _make_check(
            name="sum_gate_budtender_net_sales",
            expected=store,
            actual=round(sum(actual["budtender_sales"].values()), 2),
            tol=tol,
        ),
        _make_check(
            name="sum_gate_brand_net_sales",
            expected=store,
            actual=round(sum(actual["brand_summary"].values()), 2),
            tol=tol,
        ),
        _make_check(
            name="sum_gate_daily_net_sales",
            expected=store,
            actual=round(sum(actual["discounts_over_time"].values()), 2),
            tol=tol,
        ),
    ]
    return checks


def run_reference_checks(
    actual: dict[str, Any],
    reference: dict[str, Any],
    tol: Tolerance,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    ref_store = reference.get("store") or {}
    if "net_sales" in ref_store:
        checks.append(
            _make_check(
                name="ref_store_net_sales",
                expected=_parse_float(ref_store["net_sales"]),
                actual=actual["store_net_sales"],
                tol=tol,
            )
        )
    else:
        checks.append({
            "name": "ref_store_net_sales",
            "status": "warning",
            "expected": None,
            "actual": actual["store_net_sales"],
            "delta_abs": None,
            "delta_pct": None,
            "tolerance": tol.money_abs,
            "tolerance_pct": tol.pct,
            "blocking": False,
            "message": "reference missing store net_sales",
        })

    ref_bt = reference.get("budtender_sales") or {}
    if ref_bt:
        for name, metrics in sorted(ref_bt.items()):
            if "net_sales" not in metrics:
                continue
            expected = _parse_float(metrics["net_sales"])
            actual_val = actual["budtender_sales"].get(name)
            if actual_val is None:
                checks.append({
                    "name": f"ref_budtender_net_sales:{name}",
                    "status": "fail",
                    "expected": expected,
                    "actual": None,
                    "delta_abs": None,
                    "delta_pct": None,
                    "tolerance": tol.money_abs,
                    "tolerance_pct": tol.pct,
                    "blocking": True,
                    "message": "budtender missing in dashboard",
                })
                continue
            checks.append(
                _make_check(
                    name=f"ref_budtender_net_sales:{name}",
                    expected=expected,
                    actual=actual_val,
                    tol=tol,
                )
            )
    else:
        checks.append({
            "name": "ref_budtender_net_sales",
            "status": "warning",
            "expected": None,
            "actual": None,
            "delta_abs": None,
            "delta_pct": None,
            "tolerance": tol.money_abs,
            "tolerance_pct": tol.pct,
            "blocking": False,
            "message": "reference has no budtender rows",
        })

    ref_daily = reference.get("discounts_over_time") or {}
    if ref_daily:
        for day, metrics in sorted(ref_daily.items()):
            if "net_sales" not in metrics:
                continue
            expected = _parse_float(metrics["net_sales"])
            actual_val = actual["discounts_over_time"].get(day)
            if actual_val is None:
                checks.append({
                    "name": f"ref_daily_net_sales:{day}",
                    "status": "fail",
                    "expected": expected,
                    "actual": None,
                    "delta_abs": None,
                    "delta_pct": None,
                    "tolerance": tol.money_abs,
                    "tolerance_pct": tol.pct,
                    "blocking": True,
                    "message": "date missing in dashboard",
                })
                continue
            checks.append(
                _make_check(
                    name=f"ref_daily_net_sales:{day}",
                    expected=expected,
                    actual=actual_val,
                    tol=tol,
                )
            )

    ref_brand = reference.get("brand_summary") or {}
    if ref_brand:
        for brand, metrics in sorted(ref_brand.items()):
            if "net_sales" not in metrics:
                continue
            expected = _parse_float(metrics["net_sales"])
            actual_val = actual["brand_summary"].get(brand)
            if actual_val is None:
                # try brand_name alias match
                actual_val = next(
                    (v for k, v in actual["brand_summary"].items() if k.lower() == brand.lower()),
                    None,
                )
            if actual_val is None:
                checks.append({
                    "name": f"ref_brand_net_sales:{brand}",
                    "status": "fail",
                    "expected": expected,
                    "actual": None,
                    "delta_abs": None,
                    "delta_pct": None,
                    "tolerance": tol.money_abs,
                    "tolerance_pct": tol.pct,
                    "blocking": True,
                    "message": "brand missing in dashboard",
                })
                continue
            checks.append(
                _make_check(
                    name=f"ref_brand_net_sales:{brand}",
                    expected=expected,
                    actual=actual_val,
                    tol=tol,
                )
            )

    ref_cat = reference.get("budtender_by_category") or {}
    for key, metrics in sorted(ref_cat.items()):
        if "net_sales" not in metrics:
            continue
        expected = _parse_float(metrics["net_sales"])
        actual_val = actual["budtender_by_category"].get(key)
        if actual_val is None:
            checks.append({
                "name": f"ref_category_budtender_net_sales:{key}",
                "status": "warning",
                "expected": expected,
                "actual": None,
                "delta_abs": None,
                "delta_pct": None,
                "tolerance": tol.money_abs,
                "tolerance_pct": tol.pct,
                "blocking": False,
                "message": "category/budtender row missing in dashboard",
            })
            continue
        checks.append(
            _make_check(
                name=f"ref_category_budtender_net_sales:{key}",
                expected=expected,
                actual=actual_val,
                tol=tol,
                blocking=False,
            )
        )
    return checks


def aggregate_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for c in checks if c["status"] == "pass")
    failed = sum(1 for c in checks if c["status"] == "fail")
    warnings = sum(1 for c in checks if c["status"] == "warning")
    abs_deltas = [abs(c["delta_abs"]) for c in checks if isinstance(c.get("delta_abs"), (int, float))]
    pct_deltas = [abs(c["delta_pct"]) for c in checks if isinstance(c.get("delta_pct"), (int, float))]
    return {
        "checks_total": len(checks),
        "checks_passed": passed,
        "checks_failed": failed,
        "checks_warning": warnings,
        "max_abs_delta": max(abs_deltas) if abs_deltas else 0.0,
        "max_pct_delta": max(pct_deltas) if pct_deltas else 0.0,
    }


def overall_status(checks: list[dict[str, Any]]) -> str:
    if any(c["status"] == "fail" for c in checks):
        return "fail"
    if any(c["status"] == "warning" for c in checks):
        return "warning"
    return "pass"


def build_report(
    *,
    dashboard: dict[str, Any],
    reference: dict[str, Any] | None,
    reference_type: str | None,
    reference_path: Path | None,
    tol: Tolerance,
) -> dict[str, Any]:
    actual = _extract_actual(dashboard)
    checks = run_sum_gate_checks(actual, tol)
    if reference is not None:
        checks.extend(run_reference_checks(actual, reference, tol))

    summary = aggregate_summary(checks)
    period = (dashboard.get("meta") or {}).get("period") or {}
    if reference and reference.get("period"):
        ref_period = reference["period"]
        if ref_period:
            period = ref_period

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": overall_status(checks),
        "period": period,
        "reference": {
            "type": reference_type,
            "path": str(reference_path) if reference_path else None,
        },
        "dashboard": {
            "path": None,
        },
        "tolerance": {
            "money_abs": tol.money_abs,
            "pct": tol.pct,
        },
        "summary": summary,
        "checks": checks,
    }


def reconcile(
    dashboard: dict[str, Any],
    *,
    reference: dict[str, Any] | None = None,
    reference_type: str | None = None,
    reference_path: Path | None = None,
    tol: Tolerance | None = None,
) -> dict[str, Any]:
    tolerance = tol or Tolerance()
    return build_report(
        dashboard=dashboard,
        reference=reference,
        reference_type=reference_type,
        reference_path=reference_path,
        tol=tolerance,
    )


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def exit_code_for_report(report: dict[str, Any], *, strict: bool = False) -> int:
    status = report.get("status")
    if status == "pass":
        return 0
    if status == "fail":
        return 1
    if strict and status == "warning":
        return 1
    return 0


def load_reconciliation_report(path: Path | None = None) -> dict[str, Any] | None:
    p = path or DEFAULT_REPORT_JSON
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def reconciliation_status_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    """Compact status for API / Command Center trust strip."""
    if not report:
        return {
            "status": "missing",
            "generated_at": None,
            "reference": {"type": None, "path": None},
            "summary": None,
            "failed_checks": [],
            "message": "No reconciliation report yet — run scripts/reconcile_retail_dashboard.py after dashboard build.",
        }

    failed = [
        {
            "name": c["name"],
            "expected": c.get("expected"),
            "actual": c.get("actual"),
            "delta_abs": c.get("delta_abs"),
            "message": c.get("message"),
        }
        for c in report.get("checks") or []
        if c.get("status") == "fail"
    ]
    status = report.get("status") or "unknown"
    ref = report.get("reference") or {}
    messages = {
        "pass": "Operations metrics reconciled — safe to use.",
        "fail": f"Reconciliation failed ({len(failed)} blocking check(s)) — do not rely on Operations metrics.",
        "warning": "Reconciliation passed with warnings — review before operational use.",
    }
    return {
        "status": status,
        "generated_at": report.get("generated_at"),
        "period": report.get("period"),
        "reference": {
            "type": ref.get("type"),
            "path": ref.get("path"),
        },
        "summary": report.get("summary"),
        "failed_checks": failed[:10],
        "message": messages.get(status, "Reconciliation status unknown."),
    }
