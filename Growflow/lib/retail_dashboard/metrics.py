"""
Aggregate fact-store rows into retail dashboard widget payloads.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from lib.growflow_config import load_config


def _row_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)


def _cents_to_usd(cents: int) -> float:
    return round(cents / 100.0, 2)


def _safe_pct(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return round(100.0 * num / den, 2)


def _period_dates(preset: str, tz: ZoneInfo, end: date | None = None) -> tuple[date, date]:
    end_d = end or datetime.now(tz).date()
    if preset == "last_7_days":
        start_d = end_d - timedelta(days=6)
    elif preset == "last_90_days":
        start_d = end_d - timedelta(days=89)
    else:  # last_30_days default
        start_d = end_d - timedelta(days=29)
    return start_d, end_d


def prior_period(start: date, end: date) -> tuple[date, date]:
    days = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=days - 1)
    return prior_start, prior_end


@dataclass
class DashboardPayload:
    meta: dict[str, Any]
    period_compare_kpis: list[dict[str, Any]]
    budtender_sales: list[dict[str, Any]]
    discounts_over_time: list[dict[str, Any]]
    budtender_by_category: list[dict[str, Any]]
    brand_summary: list[dict[str, Any]]
    alerts: list[dict[str, Any]]


def _line_net_cents(row: dict[str, Any]) -> int:
    if row.get("is_return"):
        return -abs(int(row.get("net_price_cents") or 0))
    return int(row.get("net_price_cents") or 0)


def _line_gross_cents(row: dict[str, Any]) -> int:
    if row.get("is_return"):
        return -abs(int(row.get("gross_price_cents") or 0))
    return int(row.get("gross_price_cents") or 0)


def build_dashboard(
    lines: list[Any],
    *,
    period_start: date,
    period_end: date,
    prior_start: date | None = None,
    prior_end: date | None = None,
    store_id: str | None = None,
    channel: str = "all",
    coaching_threshold_discount_pp: float = 15.0,
    coaching_threshold_aov_pct: float = 20.0,
) -> DashboardPayload:
    cfg = load_config()
    tz = ZoneInfo(cfg.get("sales_timezone") or "America/Chicago")

    rows = [_row_dict(r) for r in lines]
    if channel and channel not in ("all", ""):
        rows = [r for r in rows if str(r.get("channel") or "") == channel]

    # --- helpers ---
    def filter_period(rlist: list[dict], start: date, end: date) -> list[dict]:
        out = []
        for r in rlist:
            d = str(r.get("sold_date_local") or "")
            if not d:
                continue
            try:
                ld = date.fromisoformat(d)
            except ValueError:
                continue
            if start <= ld <= end:
                out.append(r)
        return out

    current = filter_period(rows, period_start, period_end)
    prior: list[dict] = []
    if prior_start and prior_end:
        prior = filter_period(rows, prior_start, prior_end)

    def sum_net(rlist: list[dict]) -> int:
        return sum(_line_net_cents(r) for r in rlist)

    def sum_menu(rlist: list[dict]) -> int:
        return sum(int(r.get("original_price_cents") or r.get("collected_otd_cents") or 0) for r in rlist)

    def sum_discount(rlist: list[dict]) -> int:
        return sum(int(r.get("discount_cents") or 0) for r in rlist)

    def orders_with_discount(rlist: list[dict]) -> set[str]:
        by_order: dict[str, int] = defaultdict(int)
        for r in rlist:
            oid = str(r.get("order_object_id") or "")
            if oid:
                by_order[oid] += int(r.get("discount_cents") or 0)
        return {oid for oid, d in by_order.items() if d > 0}

    def distinct_orders(rlist: list[dict]) -> set[str]:
        return {str(r.get("order_object_id")) for r in rlist if r.get("order_object_id")}

    store_net = sum_net(current)
    store_menu = sum_menu(current)
    store_discount = sum_discount(current)
    store_orders = distinct_orders(current)
    store_disc_orders = orders_with_discount(current)

    eff_discount_pct = _safe_pct(store_discount, store_menu) or 0.0
    pct_orders_disc = _safe_pct(len(store_disc_orders), len(store_orders)) or 0.0

    # --- budtender sales ---
    bt_net: dict[str, int] = defaultdict(int)
    bt_orders: dict[str, set[str]] = defaultdict(set)
    bt_menu: dict[str, int] = defaultdict(int)
    bt_discount: dict[str, int] = defaultdict(int)
    bt_disc_orders: dict[str, set[str]] = defaultdict(set)

    for r in current:
        name = str(r.get("budtender_name") or "Unknown")
        bt_net[name] += _line_net_cents(r)
        bt_menu[name] += int(r.get("original_price_cents") or r.get("collected_otd_cents") or 0)
        bt_discount[name] += int(r.get("discount_cents") or 0)
        oid = str(r.get("order_object_id") or "")
        if oid:
            bt_orders[name].add(oid)
            if int(r.get("discount_cents") or 0) > 0:
                bt_disc_orders[name].add(oid)

    store_aov = (store_net / len(store_orders)) if store_orders else 0
    store_eff_disc = eff_discount_pct

    budtender_sales: list[dict[str, Any]] = []
    for name in sorted(bt_net.keys(), key=lambda n: bt_net[n], reverse=True):
        oc = len(bt_orders[name])
        net = bt_net[name]
        menu = bt_menu[name]
        disc = bt_discount[name]
        eff = _safe_pct(disc, menu) or 0.0
        ord_disc = _safe_pct(len(bt_disc_orders[name]), oc) or 0.0
        aov = _cents_to_usd(int(net / oc)) if oc else 0.0
        pct_net = _safe_pct(net, store_net) or 0.0
        flags: list[str] = []
        if eff > store_eff_disc + coaching_threshold_discount_pp:
            flags.append("high_discount_vs_store")
        if oc and store_aov > 0:
            aov_cents = net / oc
            if aov_cents < store_aov * (1 - coaching_threshold_aov_pct / 100):
                flags.append("low_aov_vs_store")
            if eff > store_eff_disc + coaching_threshold_discount_pp and aov_cents < store_aov * 0.85:
                flags.append("low_aov_and_high_discount")
        budtender_sales.append({
            "budtender": name,
            "net_sales": _cents_to_usd(net),
            "order_count": oc,
            "aov": aov,
            "effective_discount_pct": eff,
            "pct_orders_discounted": ord_disc,
            "pct_net_sales": pct_net,
            "flags": flags,
        })

    # --- discounts over time ---
    daily_net: dict[str, int] = defaultdict(int)
    daily_menu: dict[str, int] = defaultdict(int)
    daily_discount: dict[str, int] = defaultdict(int)
    daily_orders: dict[str, set[str]] = defaultdict(set)
    daily_disc_orders: dict[str, set[str]] = defaultdict(set)

    for r in current:
        d = str(r.get("sold_date_local"))
        daily_net[d] += _line_net_cents(r)
        daily_menu[d] += int(r.get("original_price_cents") or r.get("collected_otd_cents") or 0)
        daily_discount[d] += int(r.get("discount_cents") or 0)
        oid = str(r.get("order_object_id") or "")
        if oid:
            daily_orders[d].add(oid)
            if int(r.get("discount_cents") or 0) > 0:
                daily_disc_orders[d].add(oid)

    discounts_over_time = []
    d = period_start
    while d <= period_end:
        key = d.isoformat()
        menu = daily_menu.get(key, 0)
        disc = daily_discount.get(key, 0)
        orders = daily_orders.get(key, set())
        disc_orders = daily_disc_orders.get(key, set())
        discounts_over_time.append({
            "date": key,
            "net_sales": _cents_to_usd(daily_net.get(key, 0)),
            "effective_discount_pct": _safe_pct(disc, menu) or 0.0,
            "pct_orders_discounted": _safe_pct(len(disc_orders), len(orders)) or 0.0,
        })
        d += timedelta(days=1)

    # --- budtender by category ---
    cat_bt: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in current:
        cat = str(r.get("category_canonical") or r.get("category_raw") or "Unknown")
        bt = str(r.get("budtender_name") or "Unknown")
        cat_bt[(cat, bt)]["gross"] += _line_gross_cents(r)
        cat_bt[(cat, bt)]["net"] += _line_net_cents(r)
        cat_bt[(cat, bt)]["items"] += 1

    budtender_by_category = []
    for (cat, bt), vals in sorted(cat_bt.items(), key=lambda x: (-x[1]["net"], x[0][0], x[0][1])):
        budtender_by_category.append({
            "category_name": cat,
            "budtender": bt,
            "gross_sales": _cents_to_usd(vals["gross"]),
            "net_sales": _cents_to_usd(vals["net"]),
            "item_count": vals["items"],
        })

    # --- brand summary ---
    brand_net: dict[str, int] = defaultdict(int)
    brand_gross: dict[str, int] = defaultdict(int)
    brand_menu: dict[str, int] = defaultdict(int)
    brand_discount: dict[str, int] = defaultdict(int)
    brand_cog: dict[str, int] = defaultdict(int)
    brand_landed_cog: dict[str, int] = defaultdict(int)
    brand_returns: dict[str, int] = defaultdict(int)
    brand_raw_name: dict[str, str] = {}

    for r in current:
        b = str(r.get("brand_canonical") or r.get("brand_raw") or "Unknown")
        brand_raw_name[b] = str(r.get("brand_raw") or b)
        if r.get("is_return"):
            brand_returns[b] += abs(_line_net_cents(r))
        brand_net[b] += _line_net_cents(r)
        brand_gross[b] += _line_gross_cents(r)
        brand_menu[b] += int(r.get("original_price_cents") or 0)
        brand_discount[b] += int(r.get("discount_cents") or 0)
        cog = int(r.get("cog_cents") or 0)
        if cog > 0:
            brand_cog[b] += cog
        lc = r.get("landed_cost_cents")
        if lc is not None and int(lc) > 0:
            brand_landed_cog[b] += int(lc)

    # velocity rank by net
    ranked = sorted(brand_net.items(), key=lambda x: x[1], reverse=True)
    rank_map = {b: i + 1 for i, (b, _) in enumerate(ranked)}

    brand_summary = []
    for b, net in ranked:
        menu = brand_menu[b]
        disc = brand_discount[b]
        ret = brand_returns[b]
        native_cog = brand_cog[b]
        landed_cog = brand_landed_cog[b]
        native_margin = _safe_pct(net - native_cog, net) if native_cog else None
        landed_margin = _safe_pct(net - landed_cog, net) if landed_cog else None
        delta = None
        if native_margin is not None and landed_margin is not None:
            delta = round(landed_margin - native_margin, 2)
        brand_summary.append({
            "brand_name": brand_raw_name.get(b, b),
            "canonical_brand": b,
            "net_sales": _cents_to_usd(net),
            "returns_pct": _safe_pct(ret, abs(net) + ret) or 0.0,
            "effective_discount_pct": _safe_pct(disc, menu) or 0.0,
            "native_margin_pct": native_margin,
            "landed_margin_pct": landed_margin,
            "cog_vs_landed_delta_pct": delta,
            "profit_velocity_rank": rank_map.get(b),
        })

    # --- compare KPIs ---
    period_compare_kpis: list[dict[str, Any]] = []
    if prior:
        prior_net = sum_net(prior)
        prior_menu = sum_menu(prior)
        prior_disc = sum_discount(prior)
        prior_orders = distinct_orders(prior)
        prior_disc_orders = orders_with_discount(prior)
        comparisons = [
            ("net_sales", store_net, prior_net),
            ("effective_discount_pct", eff_discount_pct, _safe_pct(prior_disc, prior_menu) or 0),
            ("order_count", len(store_orders), len(prior_orders)),
            ("pct_orders_discounted", pct_orders_disc, _safe_pct(len(prior_disc_orders), len(prior_orders)) or 0),
        ]
        for key, cur_v, prv_v in comparisons:
            if isinstance(cur_v, float):
                delta_abs = round(cur_v - float(prv_v), 2)
                delta_pct = _safe_pct(delta_abs, float(prv_v)) if prv_v else None
                current_val = cur_v
                prior_val = float(prv_v)
            else:
                delta_abs = int(cur_v) - int(prv_v)
                delta_pct = _safe_pct(delta_abs, int(prv_v)) if prv_v else None
                current_val = int(cur_v)
                prior_val = int(prv_v)
            period_compare_kpis.append({
                "key": key,
                "current": current_val if key != "net_sales" else _cents_to_usd(int(cur_v)),
                "prior": prior_val if key != "net_sales" else _cents_to_usd(int(prv_v)),
                "delta_abs": delta_abs if key != "net_sales" else _cents_to_usd(int(delta_abs)),
                "delta_pct": delta_pct,
            })

    # --- alerts ---
    alerts: list[dict[str, Any]] = []
    if prior and eff_discount_pct > (_safe_pct(sum_discount(prior), sum_menu(prior)) or 0) + 3:
        alerts.append({
            "alert_id": "discount_spike",
            "severity": "warning",
            "code": "discount_spike",
            "message": f"Effective discount {eff_discount_pct}% vs prior period higher.",
        })
    outlier_count = sum(1 for b in budtender_sales if b.get("flags"))
    if outlier_count:
        alerts.append({
            "alert_id": "budtender_outliers",
            "severity": "info",
            "code": "budtender_outliers",
            "message": f"{outlier_count} budtender(s) flagged vs store averages.",
        })

    meta = {
        "period": {"start": period_start.isoformat(), "end": period_end.isoformat()},
        "prior_period": (
            {"start": prior_start.isoformat(), "end": prior_end.isoformat()}
            if prior_start and prior_end
            else None
        ),
        "store_id": store_id,
        "channel": channel,
        "timezone": str(tz),
        "store_net_sales": _cents_to_usd(store_net),
        "effective_discount_pct": eff_discount_pct,
        "order_count": len(store_orders),
    }

    return DashboardPayload(
        meta=meta,
        period_compare_kpis=period_compare_kpis,
        budtender_sales=budtender_sales,
        discounts_over_time=discounts_over_time,
        budtender_by_category=budtender_by_category,
        brand_summary=brand_summary,
        alerts=alerts,
    )


def validate_sums(payload: DashboardPayload) -> list[str]:
    """Return list of validation errors (empty if ok)."""
    errors: list[str] = []
    bt_total = sum(b["net_sales"] for b in payload.budtender_sales)
    brand_total = sum(b["net_sales"] for b in payload.brand_summary)
    daily_total = sum(d["net_sales"] for d in payload.discounts_over_time)
    store_total = float(payload.meta.get("store_net_sales") or 0)
    if abs(bt_total - store_total) > 1.0:
        errors.append(f"sum(budtender.net_sales)={bt_total} != store={store_total}")
    if abs(brand_total - store_total) > 1.0:
        errors.append(f"sum(brand.net_sales)={brand_total} != store={store_total}")
    if abs(daily_total - store_total) > 1.0:
        errors.append(f"sum(daily.net_sales)={daily_total} != store={store_total}")
    return errors
