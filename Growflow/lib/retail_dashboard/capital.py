"""
Capital tab payload from projection layer2 CSV (buy-plan / throughput / gross-share).

Source of truth: ``data/projection_by_category_brand_layer2_recovery.csv`` produced by
``scripts/build_projection_by_category_brand.py``.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.projection_exec_kpis import DEFAULT_HIGH_DOLLAR_USD, DEFAULT_MEANINGFUL_USD, compute_kpis, fnum
from lib.projection_dashboard_sheet_rebuilt import MEANINGFUL_USD, _kpi_definitions

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAYER2_CSV = REPO_ROOT / "data" / "projection_by_category_brand_layer2_recovery.csv"
DEFAULT_CAPITAL_JSON = REPO_ROOT / "data" / "retail_capital_latest.json"

CHART_TOP_N = 15
TABLE_TOP_N = 20


@dataclass
class CapitalPayload:
    meta: dict[str, Any]
    kpi_banner: list[dict[str, Any]]
    charts: dict[str, list[dict[str, Any]]]
    tables: dict[str, list[dict[str, Any]]]
    narrative: list[str]
    actions: list[str]
    scenario: dict[str, Any]


def load_layer2_csv(path: Path | str | None = None) -> list[dict[str, str]]:
    p = Path(path) if path else DEFAULT_LAYER2_CSV
    if not p.is_file():
        return []
    rows: list[dict[str, str]] = []
    with p.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: (v if v is not None else "") for k, v in row.items()})
    return rows


def _int_field(raw: str | None, default: int) -> int:
    if raw is None or raw == "":
        return default
    return int(float(raw))


def _scenario_from_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {
            "pool_usd": 18000,
            "velocity_days": 49,
            "cash_cycle_days": 14,
            "allocation_mode": "buy-plan",
            "days": 365,
            "remaining_unallocated_usd": None,
        }
    r0 = rows[0]
    rem = fnum(r0.get("remaining_pool_unallocated_usd"))
    return {
        "pool_usd": None,  # filled from KPI total + unallocated when buy-plan
        "velocity_days": _int_field(r0.get("velocity_window_days_run"), 49),
        "cash_cycle_days": _int_field(r0.get("cash_cycle_days_run"), 14),
        "allocation_mode": (r0.get("allocation_mode") or "buy-plan").strip(),
        "days": None,
        "remaining_unallocated_usd": rem,
    }


def _insight_bullets(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[str]:
    """Lightweight narrative (subset of sheet script semantics)."""
    bullets: list[str] = []
    total = kpis["total_pool"]
    if not rows:
        return ["No layer2 CSV found — run a capital scenario to generate projection data."]
    if kpis.get("is_buy_plan"):
        wk = kpis.get("w_avg_weeks")
        wk_s = f"{wk:.1f} weeks" if isinstance(wk, (int, float)) else "n/a"
        bullets.append(
            f"Velocity-driven buy plan: {kpis['n_rows']} funded lines deploy ${total:,.0f}; "
            f"weighted sell-through ≈ {wk_s}."
        )
    else:
        bullets.append(f"${total:,.0f} pool across {kpis['n_rows']} brand × category lines.")
    by_cat: dict[str, float] = defaultdict(float)
    for r in rows:
        by_cat[r.get("category") or "Unknown"] += fnum(r.get("allocated_cog_usd")) or 0
    if by_cat:
        top_c = max(by_cat, key=lambda k: by_cat[k])
        bullets.append(f"{top_c} carries the largest allocation (${by_cat[top_c]:,.0f}).")
    if kpis["slow_dollars"] >= 100:
        label = "CAPITAL RISK" if kpis.get("recovery_uses_days") else "slow-payback"
        bullets.append(f"${kpis['slow_dollars']:,.0f} in {label} rows — review before approving.")
    return bullets[:6]


def _action_signals(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[str]:
    out: list[str] = []
    if not rows:
        out.append("Run scenario with pool / velocity / cash-cycle sliders, then review ledger.")
        return out
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    if meaningful and kpis.get("recovery_uses_days"):
        risky = [r for r in meaningful if (fnum(r.get("cash_recovery_days")) or 0) > 21]
        if risky:
            out.append(f"Review {len(risky)} CAPITAL RISK rows (>21d recovery) before purchase orders.")
    rem = _scenario_from_rows(rows).get("remaining_unallocated_usd")
    if rem is not None and rem > 50:
        out.append(f"${rem:,.0f} pool unallocated after cash-cycle caps — consider relaxing filters or raising pool.")
    out.append("Compare fastest recovery table vs highest GP table for trade-offs.")
    return out[:5]


def _chart_pool_by_category(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_cat: dict[str, float] = defaultdict(float)
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        if a > 0:
            by_cat[r.get("category") or "Unknown"] += a
    ranked = sorted(by_cat.items(), key=lambda x: x[1], reverse=True)
    return [{"category": k, "allocated_usd": round(v, 2)} for k, v in ranked[:CHART_TOP_N]]


def _chart_brand_allocation(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_brand: dict[str, float] = defaultdict(float)
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        if a > 0:
            by_brand[r.get("brand") or "Unknown"] += a
    ranked = sorted(by_brand.items(), key=lambda x: x[1], reverse=True)
    return [{"brand": k, "allocated_usd": round(v, 2)} for k, v in ranked[:CHART_TOP_N]]


def _chart_alloc_vs_profit(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    pts = []
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        gp = fnum(r.get("projected_gross_profit_usd")) or 0
        if a >= MEANINGFUL_USD:
            pts.append({
                "brand": r.get("brand"),
                "category": r.get("category"),
                "allocated_usd": round(a, 2),
                "projected_gp_usd": round(gp, 2),
            })
    return sorted(pts, key=lambda x: x["allocated_usd"], reverse=True)[:CHART_TOP_N]


def _chart_recovery_bucket(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, float] = defaultdict(float)
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        if a <= 0:
            continue
        if kpis.get("recovery_uses_days"):
            key = (r.get("cash_cycle_status") or "UNKNOWN").strip() or "UNKNOWN"
        else:
            key = (r.get("recovery_bucket") or "Unknown").strip() or "Unknown"
        counts[key] += a
    order = ["SAFE", "WARNING", "CAPITAL RISK", "Fast (<2wk)", "Medium (1–2mo)", "Moderate (2–3mo)", "Slow (>3mo)"]
    keys = [k for k in order if k in counts] + [k for k in counts if k not in order]
    return [{"bucket": k, "allocated_usd": round(counts[k], 2)} for k in keys]


def _chart_category_recovery(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[dict[str, Any]]:
    by_cat_w: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        if a < MEANINGFUL_USD:
            continue
        cat = r.get("category") or "Unknown"
        if kpis.get("recovery_uses_days"):
            crd = fnum(r.get("cash_recovery_days"))
            if crd is None:
                continue
            n, d = by_cat_w[cat]
            by_cat_w[cat] = (n + crd * a, d + a)
        else:
            mo = fnum(r.get("months_to_recover_cog"))
            if mo is None:
                continue
            n, d = by_cat_w[cat]
            by_cat_w[cat] = (n + mo * a, d + a)
    out = []
    for cat, (num, den) in by_cat_w.items():
        if den <= 0:
            continue
        avg = num / den
        out.append({
            "category": cat,
            "avg_recovery": round(avg, 2),
            "unit": "days" if kpis.get("recovery_uses_days") else "months",
        })
    return sorted(out, key=lambda x: x["avg_recovery"])[:CHART_TOP_N]


def _table_fastest_recovery(rows: list[dict[str, str]], kpis: dict[str, Any]) -> list[dict[str, Any]]:
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    if kpis.get("recovery_uses_days") and kpis.get("is_buy_plan"):
        key_fn = lambda r: (-(fnum(r.get("avg_units_per_day")) or 0), -(fnum(r.get("allocated_cog_usd")) or 0))
    elif kpis.get("recovery_uses_days"):
        key_fn = lambda r: (fnum(r.get("cash_recovery_days")) or 1e9, -(fnum(r.get("allocated_cog_usd")) or 0))
    else:
        key_fn = lambda r: (fnum(r.get("months_to_recover_cog")) or 1e9, -(fnum(r.get("allocated_cog_usd")) or 0))
    ranked = sorted(meaningful, key=key_fn)[:TABLE_TOP_N]
    out = []
    for r in ranked:
        row = {
            "brand": r.get("brand"),
            "category": r.get("category"),
            "allocated_usd": fnum(r.get("allocated_cog_usd")),
            "projected_gp_usd": fnum(r.get("projected_gross_profit_usd")),
        }
        if kpis.get("recovery_uses_days"):
            row["cash_recovery_days"] = fnum(r.get("cash_recovery_days"))
            row["avg_units_per_day"] = fnum(r.get("avg_units_per_day"))
            row["cash_cycle_status"] = r.get("cash_cycle_status")
        else:
            row["months_to_recover"] = fnum(r.get("months_to_recover_cog"))
        out.append(row)
    return out


def _table_highest_gp(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    meaningful = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= MEANINGFUL_USD]
    ranked = sorted(meaningful, key=lambda r: -(fnum(r.get("projected_gross_profit_usd")) or 0))[:TABLE_TOP_N]
    return [
        {
            "brand": r.get("brand"),
            "category": r.get("category"),
            "allocated_usd": fnum(r.get("allocated_cog_usd")),
            "projected_gp_usd": fnum(r.get("projected_gross_profit_usd")),
            "allocation_efficiency": fnum(r.get("allocation_efficiency")),
        }
        for r in ranked
    ]


def _table_weak_efficiency(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    hi = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= DEFAULT_HIGH_DOLLAR_USD]
    with_eff = [r for r in hi if fnum(r.get("allocation_efficiency")) is not None]
    ranked = sorted(with_eff, key=lambda r: fnum(r.get("allocation_efficiency")) or 1e18)[:TABLE_TOP_N]
    return [
        {
            "brand": r.get("brand"),
            "category": r.get("category"),
            "allocated_usd": fnum(r.get("allocated_cog_usd")),
            "allocation_efficiency": fnum(r.get("allocation_efficiency")),
            "projected_gp_usd": fnum(r.get("projected_gross_profit_usd")),
        }
        for r in ranked
    ]


def _table_ledger(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    funded = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) > 0]
    ranked = sorted(funded, key=lambda r: -(fnum(r.get("allocated_cog_usd")) or 0))
    out = []
    for r in ranked:
        out.append({
            "brand": r.get("brand"),
            "category": r.get("category"),
            "allocated_usd": fnum(r.get("allocated_cog_usd")),
            "units_to_buy": fnum(r.get("units_from_allocation")),
            "projected_revenue_usd": fnum(r.get("projected_revenue_from_allocated_units_usd")),
            "projected_gp_usd": fnum(r.get("projected_gross_profit_usd")),
            "cash_cycle_status": r.get("cash_cycle_status"),
            "cover_status": r.get("cover_status"),
        })
    return out


def build_capital(
    rows: list[dict[str, str]] | None = None,
    *,
    layer2_path: Path | str | None = None,
    run_id: str | None = None,
) -> CapitalPayload:
    data = rows if rows is not None else load_layer2_csv(layer2_path)
    kpis = compute_kpis(
        data,
        meaningful_usd=DEFAULT_MEANINGFUL_USD,
        high_dollar_usd=DEFAULT_HIGH_DOLLAR_USD,
    )
    scenario = _scenario_from_rows(data)
    if scenario.get("remaining_unallocated_usd") is not None:
        scenario["pool_usd"] = round(kpis["total_pool"] + (scenario["remaining_unallocated_usd"] or 0), 2)
    else:
        scenario["pool_usd"] = round(kpis["total_pool"], 2)

    kpi_banner = []
    for label, value, kind in _kpi_definitions(kpis):
        kpi_banner.append({"label": label, "value": value, "kind": kind})

    charts = {
        "pool_by_category": _chart_pool_by_category(data),
        "brand_allocation": _chart_brand_allocation(data),
        "alloc_vs_profit": _chart_alloc_vs_profit(data),
        "recovery_bucket": _chart_recovery_bucket(data, kpis),
        "category_recovery": _chart_category_recovery(data, kpis),
    }
    tables = {
        "fastest_recovery": _table_fastest_recovery(data, kpis),
        "highest_gp": _table_highest_gp(data),
        "weak_efficiency": _table_weak_efficiency(data),
        "ledger": _table_ledger(data),
    }

    built = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    meta = {
        "run_id": run_id or f"cap_{built.replace(':', '').replace('-', '')[:15]}",
        "built_at": built,
        "source_csv": str(layer2_path or DEFAULT_LAYER2_CSV),
        "source_exists": bool(data),
        "row_count": len(data),
        "funded_row_count": kpis["n_rows"],
        "validation": {"ok": bool(data), "errors": [] if data else ["layer2_csv_missing"]},
    }

    return CapitalPayload(
        meta=meta,
        kpi_banner=kpi_banner,
        charts=charts,
        tables=tables,
        narrative=_insight_bullets(data, kpis),
        actions=_action_signals(data, kpis),
        scenario=scenario,
    )


def payload_to_dict(payload: CapitalPayload) -> dict[str, Any]:
    return {
        "meta": payload.meta,
        "kpi_banner": payload.kpi_banner,
        "charts": payload.charts,
        "tables": payload.tables,
        "narrative": payload.narrative,
        "actions": payload.actions,
        "scenario": payload.scenario,
    }
