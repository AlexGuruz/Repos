"""Growflow status and domain reads — prepared snapshot first, then GET APIs. Never refresh (B3)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import paths as pathmod
from ..errors import (
    GROWFLOW_API_UNAVAILABLE,
    GROWFLOW_SCHEMA_MISMATCH,
    GROWFLOW_SNAPSHOT_MISSING,
    GROWFLOW_SNAPSHOT_STALE,
)
from ..models import GrowflowStatusResult
from ..settings import get_settings


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _freshness_from_snapshot(
    generated_at: str | None,
    stale_flag: bool,
    stale_after_sec: int,
) -> tuple[str, list[str], str | None]:
    warnings: list[str] = []
    error_code: str | None = None
    now = datetime.now(timezone.utc)
    parsed = _parse_iso(generated_at)
    age_stale = False
    if parsed is not None:
        age = (now - parsed.astimezone(timezone.utc)).total_seconds()
        if age > stale_after_sec:
            age_stale = True
    if stale_flag or age_stale:
        warnings.append("Growflow snapshot is stale")
        error_code = GROWFLOW_SNAPSHOT_STALE
        return "stale_but_usable", warnings, error_code
    return "fresh", warnings, None


def _http_get_json(url: str, timeout: float) -> tuple[dict[str, Any] | None, str | None]:
    req = Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
    except HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "unexpected payload type"
    return payload, None


def _growflow_repo() -> Path:
    root = pathmod.growflow_root()
    if root is None:
        raise FileNotFoundError(
            "Growflow root not found. Set REPOS_ROOT or place products/growflow beside ai-lab."
        )
    return root


def _from_snapshot(payload: dict[str, Any]) -> GrowflowStatusResult:
    settings = get_settings()
    if not isinstance(payload.get("data"), dict):
        return GrowflowStatusResult(
            ok=False,
            source="prepared_snapshot",
            freshness="unavailable",
            error_code=GROWFLOW_SCHEMA_MISMATCH,
            degraded=True,
            summary="Invalid growflow_snapshot schema",
        )
    data = payload["data"]
    freshness, warnings, err = _freshness_from_snapshot(
        payload.get("generated_at"),
        bool(payload.get("stale", False)),
        settings.growflow_snapshot_stale_seconds,
    )
    blockers = data.get("known_blockers") or []
    if not isinstance(blockers, list):
        blockers = [str(blockers)]
    sales = data.get("latest_sales_summary")
    if isinstance(sales, str) and "Metric Definitions" in sales:
        blockers = list(blockers) + ["snapshot_contains_formula_docs_as_sales"]
        freshness = "degraded"
        err = GROWFLOW_SCHEMA_MISMATCH
    if isinstance(sales, dict) and sales.get("fixture_suspected"):
        blockers = list(blockers) + ["retail_dashboard_fixture_suspected"]
        freshness = "degraded"
    metrics: dict[str, Any] = {}
    for key in (
        "latest_sales_summary",
        "retail",
        "capital",
        "consignment",
        "projection_eod",
        "company_bi",
        "platform_status",
        "data_freshness_timestamps",
        "validation_status_by_metric",
        "dashboard_export_status",
    ):
        if key in data:
            metrics[key] = data[key]
    summary = str(payload.get("summary_short") or payload.get("summary_detailed") or "Growflow snapshot loaded")
    ok = True
    if isinstance(sales, str) and "Metric Definitions" in sales:
        ok = False
    return GrowflowStatusResult(
        ok=ok,
        source="prepared_snapshot",
        freshness=freshness if freshness in ("fresh", "stale_but_usable", "degraded", "unavailable") else "degraded",  # type: ignore[arg-type]
        generated_at=payload.get("generated_at"),
        warnings=warnings + ([f"blockers: {blockers}"] if blockers else []),
        error_code=err,
        degraded=freshness != "fresh" or not ok,
        summary=summary,
        metrics=metrics,
        known_blockers=[str(b) for b in blockers],
    )


def _from_retail_api() -> GrowflowStatusResult:
    settings = get_settings()
    url = f"{settings.growflow_api_url.rstrip('/')}/api/retail/dashboard"
    payload, err = _http_get_json(url, settings.growflow_http_timeout_seconds)
    if payload is None:
        return GrowflowStatusResult(
            ok=False,
            source="retail_api",
            freshness="unavailable",
            error_code=GROWFLOW_API_UNAVAILABLE,
            degraded=True,
            summary="Retail API unavailable",
            warnings=[err or "unknown"],
        )
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    trust = meta.get("trust") if isinstance(meta.get("trust"), dict) else {}
    metrics = {
        "store_net_sales": meta.get("store_net_sales"),
        "order_count": meta.get("order_count"),
        "period": meta.get("period"),
        "built_at": meta.get("built_at"),
        "validation": meta.get("validation"),
        "trust": trust,
        "run_id": meta.get("run_id"),
    }
    fixture = bool(trust.get("fixture_suspected") or meta.get("fixture_suspected"))
    freshness = str(trust.get("freshness") or "fresh")
    if fixture:
        freshness = "degraded"
    return GrowflowStatusResult(
        ok=not fixture,
        source="retail_api",
        freshness=freshness if freshness in ("fresh", "stale_but_usable", "degraded", "unavailable") else "fresh",  # type: ignore[arg-type]
        generated_at=str(meta.get("built_at")) if meta.get("built_at") else None,
        summary=(
            f"Retail dashboard net={meta.get('store_net_sales')} orders={meta.get('order_count')}"
            + (" (fixture suspected)" if fixture else "")
        ),
        metrics=metrics,
        warnings=["Served from retail API GET — not prepared snapshot"]
        + (["fixture_suspected"] if fixture else []),
        known_blockers=["retail_dashboard_fixture_suspected"] if fixture else [],
        degraded=fixture or freshness != "fresh",
    )


def get_growflow_status(*, prefer_prepared_snapshot: bool = True) -> GrowflowStatusResult:
    """B3: never calls refresh. Snapshot first, then GET dashboard."""
    if prefer_prepared_snapshot:
        snap_path = pathmod.growflow_snapshot_path()
        if snap_path.is_file():
            try:
                payload = json.loads(snap_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return GrowflowStatusResult(
                    ok=False,
                    source="prepared_snapshot",
                    freshness="unavailable",
                    error_code=GROWFLOW_SNAPSHOT_MISSING,
                    degraded=True,
                    summary="Failed to read growflow_snapshot",
                    warnings=[str(exc)],
                )
            if isinstance(payload, dict):
                return _from_snapshot(payload)
    api_result = _from_retail_api()
    if api_result.ok:
        return api_result
    if prefer_prepared_snapshot and not pathmod.growflow_snapshot_path().is_file():
        api_result.warnings = list(api_result.warnings) + ["prepared snapshot missing"]
        if api_result.error_code is None:
            api_result.error_code = GROWFLOW_SNAPSHOT_MISSING
    return api_result


def _bounded_domain_from_api(path: str, keys: tuple[str, ...]) -> GrowflowStatusResult:
    settings = get_settings()
    url = f"{settings.growflow_api_url.rstrip('/')}{path}"
    payload, err = _http_get_json(url, settings.growflow_http_timeout_seconds)
    if payload is None:
        return GrowflowStatusResult(
            ok=False,
            source="retail_api",
            freshness="unavailable",
            error_code=GROWFLOW_API_UNAVAILABLE,
            degraded=True,
            summary=f"API unavailable: {path}",
            warnings=[err or "unknown"],
        )
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    metrics: dict[str, Any] = {"meta": {k: meta.get(k) for k in ("built_at", "validation", "source_exists", "latest_date", "row_count") if k in meta}}
    for k in keys:
        if k in payload:
            val = payload[k]
            if isinstance(val, list):
                metrics[k] = val[:10]
            else:
                metrics[k] = val
    return GrowflowStatusResult(
        ok=True,
        source="retail_api",
        freshness="fresh",
        generated_at=str(meta.get("built_at")) if meta.get("built_at") else None,
        summary=f"Bounded read from {path}",
        metrics=metrics,
    )


def get_growflow_retail() -> GrowflowStatusResult:
    return _from_retail_api()


def get_growflow_capital() -> GrowflowStatusResult:
    return _bounded_domain_from_api("/api/retail/capital", ("kpi_banner", "tables", "charts"))


def get_growflow_consignment() -> GrowflowStatusResult:
    return _bounded_domain_from_api("/api/retail/consignment", ("kpi_strip", "active_transfers", "latest_day_by_vendor"))


def get_growflow_projection() -> GrowflowStatusResult:
    settings = get_settings()
    # Prefer platform v1 then local file
    payload, err = _http_get_json(
        f"{settings.growflow_api_url.rstrip('/')}/api/v1/projection",
        settings.growflow_http_timeout_seconds,
    )
    if payload is not None:
        return GrowflowStatusResult(
            ok=True,
            source="retail_api",
            freshness="fresh",
            generated_at=str(payload.get("as_of_local") or payload.get("generated_at")),
            summary="EOD sales projection",
            metrics={
                k: payload.get(k)
                for k in (
                    "sales_date",
                    "as_of_local",
                    "collected_so_far_cents",
                    "pace_eod_cents",
                    "base_eod_cents",
                    "order_count",
                    "conservative_cents",
                    "aggressive_cents",
                    "trust",
                )
                if k in payload or k == "trust"
            },
        )
    path = _growflow_repo() / "data" / "sales_projection_latest.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return GrowflowStatusResult(
                ok=False,
                source="local_json",
                freshness="unavailable",
                degraded=True,
                summary="Failed to read sales_projection_latest.json",
                warnings=[str(exc)],
            )
        return GrowflowStatusResult(
            ok=True,
            source="local_json",
            freshness="stale_but_usable",
            generated_at=str(payload.get("as_of_local")),
            summary="EOD projection from local JSON (API unavailable)",
            metrics={
                k: payload.get(k)
                for k in (
                    "sales_date",
                    "collected_so_far_cents",
                    "pace_eod_cents",
                    "base_eod_cents",
                    "order_count",
                )
            },
            warnings=[err or "api_v1_projection_unavailable"],
        )
    return GrowflowStatusResult(
        ok=False,
        source="local_json",
        freshness="unavailable",
        degraded=True,
        summary="sales_projection_latest.json missing",
        warnings=[err or "missing"],
    )


def get_growflow_bi_summary() -> GrowflowStatusResult:
    settings = get_settings()
    payload, err = _http_get_json(
        f"{settings.growflow_api_url.rstrip('/')}/api/v1/bi",
        settings.growflow_http_timeout_seconds,
    )
    if payload is not None:
        return GrowflowStatusResult(
            ok=bool(payload.get("ok", True)),
            source="retail_api",
            freshness="fresh",
            generated_at=str(payload.get("built_at") or (payload.get("meta") or {}).get("built_at")),
            summary=str(payload.get("summary") or "Company BI report"),
            metrics={"summary": payload.get("summary"), "meta": payload.get("meta"), "sections": payload.get("sections")},
        )
    path = _growflow_repo() / "data" / "company_bi_report_latest.json"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return GrowflowStatusResult(
                ok=False,
                source="local_json",
                freshness="unavailable",
                degraded=True,
                summary="Failed to read company_bi_report_latest.json",
                warnings=[str(exc)],
            )
        return GrowflowStatusResult(
            ok=bool(payload.get("ok", True)),
            source="local_json",
            freshness="stale_but_usable",
            summary=str(payload.get("summary") or "Company BI from local JSON"),
            metrics=payload if isinstance(payload, dict) else {},
            warnings=[err or "api_v1_bi_unavailable"],
        )
    return GrowflowStatusResult(
        ok=False,
        source="local_json",
        freshness="unavailable",
        degraded=True,
        summary="company_bi_report_latest.json missing — run scripts/build_company_bi_report.py",
        warnings=[err or "missing"],
        known_blockers=["company_bi_not_built"],
    )


def get_growflow_catalog() -> GrowflowStatusResult:
    catalog_path = pathmod.ai_lab_root() / "registry" / "growflow_read_surfaces" / "catalog.json"
    if not catalog_path.is_file():
        return GrowflowStatusResult(
            ok=False,
            source="catalog",
            freshness="unavailable",
            degraded=True,
            summary="growflow_read_surfaces catalog missing",
        )
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return GrowflowStatusResult(
            ok=False,
            source="catalog",
            freshness="unavailable",
            degraded=True,
            summary="Failed to read catalog.json",
            warnings=[str(exc)],
        )
    surfaces = payload.get("surfaces") if isinstance(payload, dict) else None
    summary_rows = []
    if isinstance(surfaces, list):
        for s in surfaces:
            if isinstance(s, dict):
                summary_rows.append(
                    {
                        "surface_id": s.get("surface_id"),
                        "metric_id": s.get("metric_id"),
                        "tools": [
                            r.get("id")
                            for r in (s.get("ask_time_reads") or [])
                            if isinstance(r, dict) and r.get("kind") == "operator_tool"
                        ],
                        "freshness_sla_seconds": s.get("freshness_sla_seconds"),
                    }
                )
    return GrowflowStatusResult(
        ok=True,
        source="catalog",
        freshness="fresh",
        summary=f"Growflow read catalog — {len(summary_rows)} surfaces",
        metrics={"version": payload.get("version"), "policy": payload.get("policy"), "surfaces": summary_rows},
    )
