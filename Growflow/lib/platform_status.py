"""
Platform status registry + freshness / fixture detectors.

Any surface that answers humans or AI must carry freshness and refuse
\"healthy\" when fixture-scale or stale past SLO.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.platform_config import GrowflowPlatformConfig, load_platform_config

STATUS_SCHEMA_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        raw = ts
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def age_seconds(ts: str | None, *, now: datetime | None = None) -> float | None:
    parsed = parse_iso(ts)
    if parsed is None:
        return None
    ref = now or datetime.now(timezone.utc)
    return max(0.0, (ref - parsed.astimezone(timezone.utc)).total_seconds())


def file_mtime_iso(path: Path) -> str | None:
    if not path.is_file():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def is_fixture_dashboard(
    meta: dict[str, Any] | None,
    *,
    cfg: GrowflowPlatformConfig | None = None,
) -> bool:
    """Detect sample/fixture retail payloads that must not report healthy."""
    cfg = cfg or load_platform_config()
    if not isinstance(meta, dict):
        return False
    if meta.get("fixture") is True:
        return True
    order_count = meta.get("order_count")
    net = meta.get("store_net_sales")
    try:
        oc = int(order_count) if order_count is not None else None
        ns = float(net) if net is not None else None
    except (TypeError, ValueError):
        return False
    if oc is None or ns is None:
        return False
    return oc <= cfg.fixture_order_count_max and ns < cfg.fixture_net_sales_max


def freshness_label(age: float | None, slo_seconds: int) -> str:
    if age is None:
        return "unavailable"
    if age <= slo_seconds:
        return "fresh"
    if age <= slo_seconds * 2:
        return "stale_but_usable"
    return "degraded"


def enrich_retail_payload(
    payload: dict[str, Any],
    *,
    cfg: GrowflowPlatformConfig | None = None,
    source_path: Path | None = None,
) -> dict[str, Any]:
    """Attach trust/freshness fields to a dashboard payload (non-destructive copy)."""
    cfg = cfg or load_platform_config()
    out = dict(payload)
    meta = dict(out.get("meta") or {}) if isinstance(out.get("meta"), dict) else {}
    built_at = meta.get("built_at") or (out.get("generated_at") if isinstance(out.get("generated_at"), str) else None)
    if not built_at and source_path:
        built_at = file_mtime_iso(source_path)
    age = age_seconds(built_at)
    fixture = is_fixture_dashboard(meta, cfg=cfg)
    label = freshness_label(age, cfg.retail_slo_seconds)
    if fixture:
        label = "degraded"
    trust = {
        "org_id": cfg.org_id,
        "freshness": label,
        "age_seconds": age,
        "slo_seconds": cfg.retail_slo_seconds,
        "fixture_suspected": fixture,
        "healthy": label == "fresh" and not fixture and bool((meta.get("validation") or {}).get("ok", True)),
        "source_paths": [str(source_path)] if source_path else [],
        "checked_at": now_iso(),
    }
    meta["org_id"] = meta.get("org_id") or cfg.org_id
    meta["trust"] = trust
    if fixture and not meta.get("fixture"):
        meta["fixture_suspected"] = True
    out["meta"] = meta
    return out


def _domain_from_json(
    path: Path,
    *,
    built_at_keys: tuple[str, ...],
    slo: int,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = read_json(path)
    if payload is None:
        return {
            "ok": False,
            "reason": "missing",
            "path": str(path),
            "freshness": "unavailable",
            "age_seconds": None,
        }
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    built_at = None
    for key in built_at_keys:
        if key in meta and isinstance(meta.get(key), str):
            built_at = meta[key]
            break
        if key in payload and isinstance(payload.get(key), str):
            built_at = payload[key]
            break
    if not built_at:
        built_at = file_mtime_iso(path)
    age = age_seconds(built_at)
    label = freshness_label(age, slo)
    fixture = False
    if "store_net_sales" in meta or "order_count" in meta:
        fixture = is_fixture_dashboard(meta)
        if fixture:
            label = "degraded"
    out: dict[str, Any] = {
        "ok": label in ("fresh", "stale_but_usable") and not fixture,
        "path": str(path),
        "built_at": built_at,
        "age_seconds": age,
        "freshness": label,
        "fixture_suspected": fixture,
        "validation_ok": bool((meta.get("validation") or {}).get("ok", True)) if meta else True,
    }
    if extra:
        out.update(extra)
    if fixture:
        out["ok"] = False
        out["reason"] = "fixture_suspected"
    elif label not in ("fresh", "stale_but_usable"):
        out["reason"] = "stale"
    return out


def build_platform_status(cfg: GrowflowPlatformConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_platform_config()
    retail = _domain_from_json(
        cfg.retail_dashboard_json,
        built_at_keys=("built_at", "generated_at"),
        slo=cfg.retail_slo_seconds,
    )
    capital = _domain_from_json(
        cfg.capital_json,
        built_at_keys=("built_at",),
        slo=cfg.capital_slo_seconds,
    )
    consign = _domain_from_json(
        cfg.consignment_json,
        built_at_keys=("built_at", "latest_date"),
        slo=cfg.consignment_slo_seconds,
    )
    # Prefer live consignment state when present
    state_path = cfg.data_dir / "consignment_state.json"
    state = read_json(state_path)
    if state:
        last_sales = state.get("last_processed_sales_date")
        last_run = state.get("last_run_at") or state.get("last_sheet_refresh_at")
        age = age_seconds(last_run if isinstance(last_run, str) else None)
        label = freshness_label(age, cfg.consignment_slo_seconds)
        consign = {
            "ok": label in ("fresh", "stale_but_usable"),
            "path": str(state_path),
            "built_at": last_run,
            "last_sales_date": last_sales,
            "age_seconds": age,
            "freshness": label,
            "source_db_exists": cfg.consignment_db.is_file(),
            "cc_json_path": str(cfg.consignment_json),
            "cc_json_freshness": consign.get("freshness"),
        }
        if label not in ("fresh", "stale_but_usable"):
            consign["reason"] = "stale"

    projection = _domain_from_json(
        cfg.sales_projection_json,
        built_at_keys=("as_of_local", "generated_at"),
        slo=cfg.projection_slo_seconds,
    )
    bi = _domain_from_json(
        cfg.company_bi_json,
        built_at_keys=("built_at", "generated_at"),
        slo=cfg.capital_slo_seconds,
    )
    transfers = {
        "ok": cfg.transfer_db.is_file(),
        "path": str(cfg.transfer_db),
        "built_at": file_mtime_iso(cfg.transfer_db),
        "age_seconds": age_seconds(file_mtime_iso(cfg.transfer_db)),
        "freshness": freshness_label(age_seconds(file_mtime_iso(cfg.transfer_db)), cfg.capital_slo_seconds)
        if cfg.transfer_db.is_file()
        else "unavailable",
    }
    if not transfers["ok"]:
        transfers["reason"] = "missing"

    register_state = read_json(cfg.data_dir / "register_close_taxes_state.json")
    register_close = {
        "ok": bool(register_state),
        "path": str(cfg.data_dir / "register_close_taxes_state.json"),
        "last_poll_at": (register_state or {}).get("last_poll_at"),
        "last_notified_at": (register_state or {}).get("last_notified_at"),
        "freshness": freshness_label(
            age_seconds((register_state or {}).get("last_poll_at")),
            cfg.retail_slo_seconds,
        )
        if register_state
        else "unavailable",
    }

    domains = {
        "retail_dashboard": retail,
        "capital": capital,
        "consignment": consign,
        "projection_eod": projection,
        "transfers": transfers,
        "company_bi": bi,
        "register_close": register_close,
    }
    slo_breaches: list[dict[str, Any]] = []
    for name, info in domains.items():
        if not info.get("ok"):
            slo_breaches.append(
                {
                    "domain": name,
                    "reason": info.get("reason") or info.get("freshness"),
                    "age_seconds": info.get("age_seconds"),
                }
            )

    return {
        "schema_version": STATUS_SCHEMA_VERSION,
        "org_id": cfg.org_id,
        "generated_at": now_iso(),
        "timezone": cfg.timezone,
        "domains": domains,
        "slo_breaches": slo_breaches,
        "overall_ok": len(slo_breaches) == 0,
    }


def write_platform_status(
    path: Path | None = None,
    *,
    cfg: GrowflowPlatformConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_platform_config()
    out_path = path or cfg.platform_status_json
    status = build_platform_status(cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    return status


def load_platform_status(cfg: GrowflowPlatformConfig | None = None) -> dict[str, Any]:
    cfg = cfg or load_platform_config()
    existing = read_json(cfg.platform_status_json)
    if existing:
        return existing
    return build_platform_status(cfg)
