"""
Executive KPI math for projection dashboards — computed in Python, not Google Sheets.

Sheets displays values pushed to ``dashboard_data`` (and duplicate snapshot columns on ``raw_layer2`` CSV).
These metrics reflect the **full layer2 CSV** (not the dashboard L1:Q1 filter).
"""
from __future__ import annotations

from typing import Any

DEFAULT_MEANINGFUL_USD = 25.0
DEFAULT_HIGH_DOLLAR_USD = 500.0


def fnum(x: str | None) -> float | None:
    if x is None or str(x).strip() == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def use_cash_recovery_days_axis(rows: list[dict[str, str]]) -> bool:
    if not rows or (rows[0].get("allocation_mode") or "").strip() != "buy-plan":
        return False
    return any(fnum(r.get("cash_recovery_days")) is not None for r in rows)


def compute_kpis(
    rows: list[dict[str, str]],
    *,
    meaningful_usd: float = DEFAULT_MEANINGFUL_USD,
    high_dollar_usd: float = DEFAULT_HIGH_DOLLAR_USD,
) -> dict[str, Any]:
    """Same semantics as legacy sheet KPI block: full-CSV aggregates and row-selection labels."""
    empty = {
        "total_pool": 0.0,
        "total_rev": 0.0,
        "total_gp": 0.0,
        "w_avg_mo": None,
        "w_avg_cash_days": None,
        "recovery_uses_days": False,
        "is_buy_plan": False,
        "total_units_buy": 0.0,
        "w_avg_weeks": None,
        "n_rows": 0,
        "n_meaningful": 0,
        "slow_dollars": 0.0,
        "largest_txt": "—",
        "high_gp_txt": "—",
        "fastest_major_txt": "—",
        "hi_eff_txt": "—",
        "lo_eff_txt": "—",
    }
    if not rows:
        return empty

    is_buy_plan = (rows[0].get("allocation_mode") or "").strip() == "buy-plan"
    recovery_uses_days = use_cash_recovery_days_axis(rows)
    total_alloc = sum(fnum(r.get("allocated_cog_usd")) or 0 for r in rows)
    total_rev = sum(fnum(r.get("projected_revenue_from_allocated_units_usd")) or 0 for r in rows)
    total_gp = sum(fnum(r.get("projected_gross_profit_usd")) or 0 for r in rows)
    total_units_buy = sum(fnum(r.get("units_from_allocation")) or 0 for r in rows)
    w_wk_n = 0.0
    w_wk_d = 0.0
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        w = fnum(r.get("weeks_to_sell_through"))
        if w is not None and a > 0:
            w_wk_n += w * a
            w_wk_d += a
    w_avg_weeks = w_wk_n / w_wk_d if w_wk_d > 0 else None
    w_mo_num = 0.0
    w_mo_den = 0.0
    w_day_num = 0.0
    w_day_den = 0.0
    slow_dollars = 0.0
    meaningful_n = 0
    for r in rows:
        a = fnum(r.get("allocated_cog_usd")) or 0
        mo = fnum(r.get("months_to_recover_cog"))
        crd = fnum(r.get("cash_recovery_days"))
        gpv = fnum(r.get("projected_gross_profit_usd"))
        if a >= meaningful_usd:
            meaningful_n += 1
        if recovery_uses_days:
            # Weighted "payback" for buy-plan day view: COG × cash-cycle days / gross profit $/row
            # (raw cash_recovery_days is capped and clusters near the cash-cycle horizon).
            pbd = None
            if crd is not None and gpv is not None and gpv > 0 and a > 0:
                pbd = (a * crd) / gpv
            if pbd is not None and a > 0:
                w_day_num += pbd * a
                w_day_den += a
            if pbd is not None and pbd > 21.0 and a > 0:
                slow_dollars += a
        else:
            if mo is not None and a > 0:
                w_mo_num += mo * a
                w_mo_den += a
            if mo is not None and mo > 4 and a > 0:
                slow_dollars += a

    w_avg_mo = w_mo_num / w_mo_den if w_mo_den else None
    w_avg_cash_days = w_day_num / w_day_den if w_day_den else None

    largest = max(rows, key=lambda r: fnum(r.get("allocated_cog_usd")) or 0)
    la = fnum(largest.get("allocated_cog_usd")) or 0
    largest_txt = f"{largest.get('brand')} · {largest.get('category')} · ${la:,.0f}"

    high_gp = max(rows, key=lambda r: fnum(r.get("projected_gross_profit_usd")) or -1e18)
    gp_v = fnum(high_gp.get("projected_gross_profit_usd")) or 0
    high_gp_txt = f"{high_gp.get('brand')} · {high_gp.get('category')} · ${gp_v:,.0f} profit"

    mean_rows = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= meaningful_usd]
    mean_eff_rows = [r for r in mean_rows if fnum(r.get("allocation_efficiency")) is not None]
    fastest_major_txt = "—"
    if mean_rows:
        if recovery_uses_days:
            if is_buy_plan:
                with_u = [r for r in mean_rows if fnum(r.get("avg_units_per_day")) is not None]
                if with_u:
                    best = max(
                        with_u,
                        key=lambda r: (
                            fnum(r.get("avg_units_per_day")) or 0.0,
                            fnum(r.get("allocated_cog_usd")) or 0.0,
                        ),
                    )
                    u = fnum(best.get("avg_units_per_day")) or 0.0
                    ba = fnum(best.get("allocated_cog_usd")) or 0.0
                    fastest_major_txt = (
                        f"{best.get('brand')} · {best.get('category')} · {u:.2f} units/day on ${ba:,.0f}"
                    )
            else:
                with_d = [r for r in mean_rows if fnum(r.get("cash_recovery_days")) is not None]
                if with_d:
                    best = min(
                        with_d,
                        key=lambda r: (
                            fnum(r.get("cash_recovery_days")) or 1e9,
                            -(fnum(r.get("allocated_cog_usd")) or 0),
                        ),
                    )
                    bd = fnum(best.get("cash_recovery_days")) or 0
                    ba = fnum(best.get("allocated_cog_usd")) or 0
                    fastest_major_txt = (
                        f"{best.get('brand')} · {best.get('category')} · {bd:.1f} d recovery on ${ba:,.0f}"
                    )
        else:
            with_mo = [r for r in mean_rows if fnum(r.get("months_to_recover_cog")) is not None]
            if with_mo:
                best = min(
                    with_mo,
                    key=lambda r: (
                        fnum(r.get("months_to_recover_cog")) or 1e9,
                        -(fnum(r.get("allocated_cog_usd")) or 0),
                    ),
                )
                bm = fnum(best.get("months_to_recover_cog")) or 0
                ba = fnum(best.get("allocated_cog_usd")) or 0
                fastest_major_txt = (
                    f"{best.get('brand')} · {best.get('category')} · {bm:.2f} mo payback on ${ba:,.0f}"
                )
    hi_eff_txt = "—"
    if mean_eff_rows:
        hi_eff = max(mean_eff_rows, key=lambda r: fnum(r.get("allocation_efficiency")) or -1)
        he = fnum(hi_eff.get("allocation_efficiency")) or 0
        hi_eff_txt = f"{hi_eff.get('brand')} · {hi_eff.get('category')} · {he:.2f} revenue per $1 COG"

    lo_eff_txt = "—"
    hi_dollar = [r for r in rows if (fnum(r.get("allocated_cog_usd")) or 0) >= high_dollar_usd]
    hi_dollar_ef = [r for r in hi_dollar if fnum(r.get("allocation_efficiency")) is not None]
    if hi_dollar_ef:
        lo_eff = min(hi_dollar_ef, key=lambda r: fnum(r.get("allocation_efficiency")) or 1e18)
        le = fnum(lo_eff.get("allocation_efficiency")) or 0
        la2 = fnum(lo_eff.get("allocated_cog_usd")) or 0
        lo_eff_txt = (
            f"{lo_eff.get('brand')} · {lo_eff.get('category')} · ${la2:,.0f} at {le:.2f} rev/$1 COG"
        )

    return {
        "total_pool": total_alloc,
        "total_rev": total_rev,
        "total_gp": total_gp,
        "w_avg_mo": w_avg_mo,
        "w_avg_cash_days": w_avg_cash_days,
        "recovery_uses_days": recovery_uses_days,
        "is_buy_plan": is_buy_plan,
        "total_units_buy": total_units_buy,
        "w_avg_weeks": w_avg_weeks,
        "n_rows": len(rows),
        "n_meaningful": meaningful_n,
        "slow_dollars": slow_dollars,
        "largest_txt": largest_txt,
        "high_gp_txt": high_gp_txt,
        "fastest_major_txt": fastest_major_txt,
        "hi_eff_txt": hi_eff_txt,
        "lo_eff_txt": lo_eff_txt,
    }


def kpi_ac_column_values(kpis: dict[str, Any]) -> list[Any]:
    """
    Values for ``dashboard_data`` KPI column AC, same row order as ``kpi_defs`` /
    former ``kpi_formulas`` output.
    """
    use_days = bool(kpis["recovery_uses_days"])
    is_buy_plan = bool(kpis["is_buy_plan"])
    out: list[Any] = []
    out.append(kpis["total_pool"])
    out.append(kpis["total_rev"])
    out.append(kpis["total_gp"])
    if is_buy_plan:
        out.append(kpis["total_units_buy"])
        wk = kpis.get("w_avg_weeks")
        out.append(round(wk, 2) if isinstance(wk, (int, float)) else "")
    w_avg_rec = kpis["w_avg_cash_days"] if use_days else kpis["w_avg_mo"]
    out.append(round(w_avg_rec, 2) if isinstance(w_avg_rec, (int, float)) else "")
    out.append(kpis["largest_txt"])
    out.append(kpis["fastest_major_txt"])
    out.append(kpis["high_gp_txt"])
    out.append(round(kpis["slow_dollars"], 2))
    out.append(kpis["hi_eff_txt"])
    out.append(kpis["lo_eff_txt"])
    return out
