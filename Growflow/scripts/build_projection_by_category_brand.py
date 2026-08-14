"""
Build a markdown projection for a fixed pool (default **$18k**).

**Default (`--allocation-mode buy-plan`):** either **SKU-first receipt-aware** reorder (when transfer DB
+yield non-zero SKU targets: per-`Product.objectId` receipt + sell-through, then pool split proportional to
SKU COG targets) or legacy **cash-cycle** deployment (rank by score, cap each line at **`--cash-cycle-days`**
of COG at recent daily burn). Layer2 adds **demand windows** (7/14/21 d units) and **cover_status** alongside
**cash_cycle_status** (SAFE / WARNING / CAPITAL RISK).

**Limits (do not “prompt away”):** Grouping is **brand × format bucket** (inferred category), not
validated `findProductCategories` / `findProducts`. Brand labels come from order-line `Product.Brand`,
not a normalized `findBrands` join. **One order line = one unit** (no line qty from API). Package
/pack-size realism and optional on-hand shelf-out signals are still limited (see
`docs/GROWFLOW_PLANNER_DATA_MAPPING.md`); SKU-first uses transfer receipt **Product.objectId** + order lines.

Legacy modes: **`throughput`** (top-N monthly COG pace + proportional split) and **`gross-share`**
(split every cell by trailing gross).

Usage (repo root):
  PYTHONPATH=. python scripts/build_projection_by_category_brand.py
  PYTHONPATH=. python scripts/build_projection_by_category_brand.py --velocity-days 49 --min-units-per-week 3
  # Legacy: proportional gross across all cells:
  PYTHONPATH=. python scripts/build_projection_by_category_brand.py --allocation-mode gross-share --pool-top-n 0
  # Same data pull: compare buy-plan vs throughput vs gross-share (internal evaluation):
  PYTHONPATH=. python scripts/build_projection_by_category_brand.py --compare-modes

Scenario knobs: `docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md`.
"""
from __future__ import annotations

import argparse
from typing import Any
import csv
import math
import os
import sqlite3
import re
import sys
import time
from collections import defaultdict
from statistics import median
import time as time_module
from datetime import date, datetime, timedelta, timezone
from datetime import time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.allocate_stock_pool import (
    allocate_pool_cents_largest_remainder,
    iter_sold_at_date_chunks,
    order_item_key,
    validate_allocation,
)
from lib.brand_merit_pool import (
    brand_label_from_line,
    cents_field,
    order_line_format_bucket,
    parse_iso_utc,
)
from lib.data_validation_gateway import validate_and_normalize
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PAGE_SIZE,
    date_range_to_where,
    fetch_paginated,
)
from lib.growflow_planner_metadata import (
    CASH_CYCLE_DAYS_DEFAULT,
    GROUPING_LEVEL as PLANNER_GROUPING_LEVEL,
    SCHEMA_SOURCE as PLANNER_SCHEMA_SOURCE,
    SCHEMA_VALIDATED as PLANNER_SCHEMA_VALIDATED,
    UNIT_MODEL_NOTE as PLANNER_UNIT_MODEL_NOTE,
)
from lib.projection_exec_kpis import compute_kpis as compute_exec_kpis_for_csv
from lib.projection_layer2_recovery import (
    avg_monthly_units_sold,
    fmt_money,
    layer2_row,
    layer2_row_buy_plan,
    usable_cog_cents,
)
from lib.projection_sku_reorder import build_sku_pre_scale_buy


def _load_latest_received_at_by_product_object_id(db_path: Path) -> dict[str, datetime]:
    """
    Read latest transfer receipt timestamp per Product.objectId from transfer receipts SQLite DB.

    Source table: product_landed_cost_current (rebuilt by scripts/build_transfer_receipts_db.py).
    Returns UTC-aware datetimes.
    """
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT product_object_id, received_at FROM product_landed_cost_current "
            "WHERE product_object_id IS NOT NULL AND TRIM(product_object_id) != '' "
            "AND received_at IS NOT NULL AND TRIM(received_at) != ''"
        )
        out: dict[str, datetime] = {}
        for pid, recv in cur.fetchall():
            k = str(pid or "").strip()
            s = str(recv or "").strip()
            if not k or not s:
                continue
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            out[k] = dt.astimezone(timezone.utc)
        return out
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _load_latest_unit_cost_cents_by_product_object_id(db_path: Path) -> dict[str, int]:
    """
    Read ``product_landed_cost_current`` from the transfer receipts SQLite DB.

    Table is built by ``scripts/build_transfer_receipts_db.py`` from Growflow transfer package lines.

    Returns mapping: product_object_id -> unit_cost_cents (rounded to nearest cent).
    """
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT product_object_id, unit_cost_cents FROM product_landed_cost_current "
            "WHERE product_object_id IS NOT NULL AND TRIM(product_object_id) != '' "
            "AND unit_cost_cents IS NOT NULL AND unit_cost_cents >= 0"
        )
        out: dict[str, int] = {}
        for pid, ucc in cur.fetchall():
            if pid is None:
                continue
            k = str(pid).strip()
            if not k:
                continue
            try:
                v = float(ucc)
            except Exception:
                continue
            if v < 0:
                continue
            out[k] = int(round(v))
        return out
    except sqlite3.Error:
        # Missing DB/table or incompatible schema; fall back to line COG.
        return {}
    finally:
        conn.close()


def _load_latest_receipt_snapshot_by_product_object_id(db_path: Path) -> dict[str, dict[str, Any]]:
    """
    Read latest receipt snapshot from product_landed_cost_current.

    Returns mapping:
      product_object_id -> {
        "received_at": UTC-aware datetime,
        "original_qty": int | None,
        "unit_cost_cents": int | None,
      }
    """
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT product_object_id, received_at, original_qty, unit_cost_cents "
            "FROM product_landed_cost_current "
            "WHERE product_object_id IS NOT NULL AND TRIM(product_object_id) != '' "
            "AND received_at IS NOT NULL AND TRIM(received_at) != ''"
        )
        out: dict[str, dict[str, Any]] = {}
        for pid, recv, oq, ucc in cur.fetchall():
            k = str(pid or "").strip()
            if not k:
                continue
            try:
                dt = datetime.fromisoformat(str(recv).replace("Z", "+00:00"))
            except Exception:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            oq_i: int | None
            try:
                oq_i = int(oq) if oq is not None else None
            except Exception:
                oq_i = None
            ucc_i: int | None
            try:
                ucc_i = int(round(float(ucc))) if ucc is not None else None
            except Exception:
                ucc_i = None
            out[k] = {
                "received_at": dt.astimezone(timezone.utc),
                "original_qty": oq_i if oq_i is None or oq_i > 0 else None,
                "unit_cost_cents": ucc_i if ucc_i is None or ucc_i >= 0 else None,
            }
        return out
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def _fetch_chunk(
    *,
    oi_query: str,
    where: dict,
    creds: str | None,
    chunk_idx: int,
    retries: int,
) -> tuple[list, str]:
    """Returns (nodes, query_used). Retries on transient network/HTML errors."""
    last_err: Exception | None = None
    query = oi_query
    for attempt in range(max(1, retries)):
        try:
            raw = fetch_paginated(
                "findOrderItems",
                query,
                {"first": PAGE_SIZE, "where": where},
                credentials_path=creds,
            )
            return raw, query
        except RuntimeError as e:
            last_err = e
            err = str(e).lower()
            if chunk_idx == 1 and attempt == 0 and ("brand" in err or "cannot query field" in err):
                query = ORDER_ITEMS_QUERY_NO_BRAND
                try:
                    raw = fetch_paginated(
                        "findOrderItems",
                        query,
                        {"first": PAGE_SIZE, "where": where},
                        credentials_path=creds,
                    )
                    return raw, query
                except RuntimeError as e2:
                    last_err = e2
            delay = min(120, 8 * (2**attempt))
            print(f"  Chunk {chunk_idx} attempt {attempt + 1}/{retries} failed: {e}; sleep {delay}s", flush=True)
            time_module.sleep(delay)
    assert last_err is not None
    raise last_err

BUCKET_DISPLAY_ORDER = [
    "Edibles",
    "Cartridges",
    "Disposables",
    "Prerolls",
    "Infused prerolls",
    "Topicals",
]

# Default brands removed from gross + $18k split (still counted in line totals).
# Consignment / non-owned inventory vendors (store policy): keep out of pool allocation.
DEFAULT_EXCLUDE_BRANDS = (
    "(no brand),Puffin Pure,710 Empire,"
    "Doc Furgsen,Doc Ferguson,Deadhead Farms,Arctic Extracts,Rooted Right Farms"
)


def parse_brand_exclusions(comma_list: str) -> frozenset[str]:
    """Case-insensitive brand labels; empty string => no exclusions."""
    return frozenset(p.strip().casefold() for p in (comma_list or "").split(",") if p.strip())


def brand_excluded(brand_label: str, excluded_casefold: frozenset[str]) -> bool:
    return brand_label.strip().casefold() in excluded_casefold


def _unique_order_items_in_local_window(
    raw: list[dict[str, Any]],
    seen: set[str],
    tz: Any,
    report_start_local: date,
    report_end_local: date,
) -> list[tuple[dict[str, Any], date]]:
    out: list[tuple[dict[str, Any], date]] = []
    for n in raw:
        k = order_item_key(n)
        if k in seen:
            continue
        sold = parse_iso_utc(n.get("SoldAt"))
        if sold is None:
            continue
        ld = sold.astimezone(tz).date()
        if ld < report_start_local or ld > report_end_local:
            continue
        seen.add(k)
        out.append((n, ld))
    return out


def implied_monthly_cog_throughput_usd(
    units: int,
    cog_cents: int,
    span_inclusive_days: int,
    *,
    cog_bearing_units: int | None = None,
) -> float | None:
    """
    Expected **dollars of COG sold per month** at the cell's trailing velocity and mix.
    Higher ⇒ more capital can clear in a short window (e.g. ~2 weeks ∝ half a month of this rate).
    """
    if units <= 0 or cog_cents <= 0:
        return None
    cog_u = cog_bearing_units if cog_bearing_units is not None else units
    if cog_u <= 0:
        return None
    aum = avg_monthly_units_sold(units, span_inclusive_days)
    if aum is None or aum <= 0:
        return None
    acu_usd = (cog_cents / 100.0) / cog_u
    if acu_usd <= 0:
        return None
    return float(aum * acu_usd)


def allocate_pool_top_n_by_recovery_throughput(
    pool_top_n: int,
    pool_cents: int,
    keys: list[tuple[str, str]],
    pair_gross: dict[tuple[str, str], int],
    pair_units: dict[tuple[str, str], int],
    pair_cog: dict[tuple[str, str], int],
    span_inclusive_days: int,
    pair_units_with_cog: dict[tuple[str, str], int] | None = None,
) -> dict[tuple[str, str], int]:
    """
    Assign the full pool to at most ``pool_top_n`` cells: rank by implied monthly COG throughput,
    then split the pool proportional to throughput among picks (largest remainder on cents).
    Unpicked cells get 0. If fewer than N cells have throughput, backfill picks by gross.
    """
    n = max(1, pool_top_n)
    out: dict[tuple[str, str], int] = {k: 0 for k in keys}
    if pool_cents <= 0 or not keys:
        return out

    scored: list[tuple[tuple[str, str], float]] = []
    for k in keys:
        t = implied_monthly_cog_throughput_usd(
            pair_units[k],
            pair_cog[k],
            span_inclusive_days,
            cog_bearing_units=(
                int(pair_units_with_cog[k])
                if pair_units_with_cog and k in pair_units_with_cog
                else None
            ),
        )
        if t is not None and t > 0:
            scored.append((k, t))
    scored.sort(
        key=lambda x: (-x[1], -pair_gross[x[0]], x[0][1].lower(), x[0][0].lower())
    )
    picked: list[tuple[str, str]] = [x[0] for x in scored[:n]]
    picked_set = set(picked)
    if len(picked) < n:
        rest = sorted(
            (k for k in keys if k not in picked_set and pair_gross[k] > 0),
            key=lambda k: (-pair_gross[k], k[1].lower(), k[0].lower()),
        )
        for k in rest:
            if len(picked) >= n:
                break
            picked.append(k)
            picked_set.add(k)

    if not picked:
        gross_keys = [k for k in keys if pair_gross[k] > 0][:n]
        if not gross_keys:
            return out
        alloc = allocate_pool_cents_largest_remainder(
            pool_cents, [1.0] * len(gross_keys)
        )
        for i, k in enumerate(gross_keys):
            out[k] = alloc[i]
        return out

    weights: list[float] = []
    for k in picked:
        t = implied_monthly_cog_throughput_usd(
            pair_units[k],
            pair_cog[k],
            span_inclusive_days,
            cog_bearing_units=(
                int(pair_units_with_cog[k])
                if pair_units_with_cog and k in pair_units_with_cog
                else None
            ),
        )
        if t is not None and t > 0:
            weights.append(t)
        else:
            weights.append(float(max(1, pair_gross[k])))
    alloc = allocate_pool_cents_largest_remainder(pool_cents, weights)
    for i, k in enumerate(picked):
        out[k] = alloc[i]
    return out


def _norm(v: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return (v - lo) / (hi - lo)


def allocate_buy_plan_pool(
    pool_cents: int,
    keys: list[tuple[str, str]],
    pair_units_recent: dict[tuple[str, str], int],
    pair_gross_recent: dict[tuple[str, str], int],
    pair_cog_recent: dict[tuple[str, str], int],
    velocity_span_days: int,
    pair_units_with_cog_recent: dict[tuple[str, str], int] | None = None,
    pair_units_per_day_recent: dict[tuple[str, str], float] | None = None,
    pair_cycle_target_units: dict[tuple[str, str], float] | None = None,
    pair_cycle_unit_cost_cents: dict[tuple[str, str], int] | None = None,
    *,
    min_units_per_week: float,
    max_funded_rows: int,
    min_allocated_cents: int,
    cash_cycle_days: float = CASH_CYCLE_DAYS_DEFAULT,
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], float]]:
    """
    **Cash-cycle allocator:** rank by score; among top ``max_funded_rows`` qualifiers, walk in priority
    order and assign ``min(max_cog_cents, remaining_pool)`` where
    ``max_cog = avg_units_per_day × cash_cycle_days × avg_cog_per_unit`` (14-day recovery cap by default).
    **No** second pass that deploys beyond that cap; **pool may be left unallocated**.

    ``min_allocated_cents`` is **ignored** here (merging small lines can violate the cash cap).

    TODO(schema truth): Swap to validated brand/category IDs and quantity semantics when SDL/playground confirm fields
    (docs/GROWFLOW_PLANNER_DATA_MAPPING.md).
    """
    out: dict[tuple[str, str], int] = {k: 0 for k in keys}
    scores: dict[tuple[str, str], float] = {k: 0.0 for k in keys}
    velocity_weeks = max(float(velocity_span_days) / 7.0, 1e-9)
    if pool_cents <= 0 or not keys:
        return out, scores

    raw: list[
        tuple[tuple[str, str], float, float, float]
    ] = []  # key, upw, weekly_cog_usd, eff
    for k in keys:
        u = int(pair_units_recent.get(k, 0))
        g = int(pair_gross_recent.get(k, 0))
        c = int(pair_cog_recent.get(k, 0))
        cog_u = (
            int(pair_units_with_cog_recent.get(k, 0))
            if pair_units_with_cog_recent
            else u
        )
        if u <= 0 or c <= 0 or cog_u <= 0:
            continue
        gross_usd = g / 100.0
        cog_usd = c / 100.0
        if pair_units_per_day_recent and k in pair_units_per_day_recent:
            upw = float(pair_units_per_day_recent[k]) * 7.0
        else:
            upw = u / velocity_weeks
        if upw < min_units_per_week:
            continue
        avg_cog = cog_usd / cog_u
        avg_ret = gross_usd / u
        if avg_cog <= 0:
            continue
        eff = avg_ret / avg_cog
        weekly_cog_usd = upw * avg_cog
        raw.append((k, float(upw), float(weekly_cog_usd), float(eff)))

    if not raw:
        return out, scores

    upws = [x[1] for x in raw]
    wcvs = [x[2] for x in raw]
    effs = [x[3] for x in raw]
    lo_u, hi_u = min(upws), max(upws)
    lo_w, hi_w = min(wcvs), max(wcvs)
    lo_e, hi_e = min(effs), max(effs)

    scored: list[tuple[tuple[str, str], float]] = []
    for k, upw, wcv, ef in raw:
        s = (
            0.4 * _norm(upw, lo_u, hi_u)
            + 0.4 * _norm(wcv, lo_w, hi_w)
            + 0.2 * _norm(ef, lo_e, hi_e)
        )
        s = max(float(s), 1e-6)
        scored.append((k, s))
        scores[k] = s

    scored.sort(key=lambda x: (-x[1], -pair_units_recent.get(x[0], 0), x[0][1].lower(), x[0][0].lower()))
    top_n = max(1, min(max_funded_rows, len(scored)))
    top = scored[:top_n]
    top_keys = [t[0] for t in top]

    max_cents_by_k: dict[tuple[str, str], int] = {}
    for k in top_keys:
        u = int(pair_units_recent.get(k, 0))
        c = int(pair_cog_recent.get(k, 0))
        cog_u = (
            int(pair_units_with_cog_recent.get(k, 0))
            if pair_units_with_cog_recent
            else u
        )
        if u <= 0 or c <= 0 or cog_u <= 0:
            max_cents_by_k[k] = 0
            continue
        cog_usd = c / 100.0
        avg_cog = cog_usd / cog_u
        if pair_cycle_target_units and k in pair_cycle_target_units:
            target_units = max(0.0, float(pair_cycle_target_units[k]))
            if pair_cycle_unit_cost_cents and k in pair_cycle_unit_cost_cents:
                uc = max(0, int(pair_cycle_unit_cost_cents[k]))
                max_cents_by_k[k] = int(math.ceil(target_units) * uc)
            else:
                max_cents_by_k[k] = int(round(target_units * avg_cog * 100.0))
            continue
        if pair_units_per_day_recent and k in pair_units_per_day_recent:
            avg_units_per_day = float(pair_units_per_day_recent[k])
        else:
            upw = u / velocity_weeks
            avg_units_per_day = float(upw) / 7.0
        max_units = avg_units_per_day * float(cash_cycle_days)
        max_cents_by_k[k] = int(round(max_units * avg_cog * 100.0))

    remaining = int(pool_cents)
    cap_left: dict[tuple[str, str], int] = {k: max(0, int(max_cents_by_k.get(k, 0))) for k in top_keys}
    active = [k for k in top_keys if cap_left.get(k, 0) > 0]
    while remaining > 0 and active:
        weights = [max(float(scores.get(k, 0.0)), 1e-6) for k in active]
        tranche = allocate_pool_cents_largest_remainder(remaining, weights)
        progressed = False
        for i, k in enumerate(active):
            want = int(tranche[i])
            if want <= 0:
                continue
            give = min(want, cap_left[k], remaining)
            if give <= 0:
                continue
            out[k] += give
            cap_left[k] -= give
            remaining -= give
            progressed = True
            if remaining <= 0:
                break
        if not progressed:
            break
        active = [k for k in active if cap_left.get(k, 0) > 0]

    return out, scores


def allocate_for_mode(
    mode: str,
    pool_cents: int,
    keys: list[tuple[str, str]],
    pair_gross: dict[tuple[str, str], int],
    pair_units: dict[tuple[str, str], int],
    pair_cog: dict[tuple[str, str], int],
    span_inclusive_days: int,
    total_fmt: int,
    pair_units_recent: dict[tuple[str, str], int],
    pair_gross_recent: dict[tuple[str, str], int],
    pair_cog_recent: dict[tuple[str, str], int],
    velocity_span: int,
    pair_units_with_cog: dict[tuple[str, str], int] | None = None,
    pair_units_with_cog_recent: dict[tuple[str, str], int] | None = None,
    pair_units_per_day_recent: dict[tuple[str, str], float] | None = None,
    pair_cycle_target_units: dict[tuple[str, str], float] | None = None,
    pair_cycle_unit_cost_cents: dict[tuple[str, str], int] | None = None,
    sku_pre_scale_cents: dict[tuple[str, str], int] | None = None,
    *,
    min_units_per_week: float,
    buy_plan_max_rows: int,
    min_allocated_cents: int,
    pool_top_n: int,
    cash_cycle_days: float = CASH_CYCLE_DAYS_DEFAULT,
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], float]]:
    """Same pool $ and keys; mode selects allocation rule (for main run or --compare-modes)."""
    planner_scores: dict[tuple[str, str], float] = {}
    if mode == "buy-plan":
        tot_sku = 0
        if sku_pre_scale_cents:
            tot_sku = sum(int(sku_pre_scale_cents.get(k, 0)) for k in keys)
        if sku_pre_scale_cents and tot_sku > 0:
            out: dict[tuple[str, str], int] = {k: 0 for k in keys}
            eligible: list[tuple[tuple[str, str], int]] = []
            for k in keys:
                pc = int(sku_pre_scale_cents.get(k, 0))
                if pc <= 0:
                    continue
                upw = (
                    float(pair_units_per_day_recent.get(k, 0.0)) * 7.0
                    if pair_units_per_day_recent
                    else 0.0
                )
                if upw < float(min_units_per_week):
                    continue
                if int(pair_units_recent.get(k, 0)) <= 0:
                    continue
                eligible.append((k, pc))
            eligible.sort(key=lambda x: -x[1])
            eligible = eligible[: max(1, int(buy_plan_max_rows))]
            if eligible:
                rk = [t[0] for t in eligible]
                weights = [float(sku_pre_scale_cents[k]) for k in rk]
                alloc = allocate_pool_cents_largest_remainder(pool_cents, weights)
                for i, k in enumerate(rk):
                    out[k] = int(alloc[i])
                return out, planner_scores
        pair_pool, planner_scores = allocate_buy_plan_pool(
            pool_cents,
            keys,
            pair_units_recent,
            pair_gross_recent,
            pair_cog_recent,
            velocity_span,
            pair_units_with_cog_recent=pair_units_with_cog_recent,
            pair_units_per_day_recent=pair_units_per_day_recent,
            pair_cycle_target_units=pair_cycle_target_units,
            pair_cycle_unit_cost_cents=pair_cycle_unit_cost_cents,
            min_units_per_week=float(min_units_per_week),
            max_funded_rows=max(1, int(buy_plan_max_rows)),
            min_allocated_cents=min_allocated_cents,
            cash_cycle_days=float(cash_cycle_days),
        )
        return pair_pool, planner_scores
    if mode == "throughput":
        n_top = int(pool_top_n) if int(pool_top_n) > 0 else 15
        pair_pool = allocate_pool_top_n_by_recovery_throughput(
            n_top,
            pool_cents,
            keys,
            pair_gross,
            pair_units,
            pair_cog,
            span_inclusive_days,
            pair_units_with_cog=pair_units_with_cog,
        )
        return pair_pool, planner_scores
    weights = [pair_gross[k] / total_fmt for k in keys]
    alloc = allocate_pool_cents_largest_remainder(pool_cents, weights)
    pair_pool = {keys[i]: alloc[i] for i in range(len(keys))}
    return pair_pool, planner_scores


def build_layer2_rows_list(
    mode: str,
    keys: list[tuple[str, str]],
    pair_pool: dict[tuple[str, str], int],
    planner_scores: dict[tuple[str, str], float],
    pair_units_recent: dict[tuple[str, str], int],
    pair_gross_recent: dict[tuple[str, str], int],
    pair_cog_recent: dict[tuple[str, str], int],
    velocity_span: int,
    pair_units_per_day_recent: dict[tuple[str, str], float] | None,
    pair_units: dict[tuple[str, str], int],
    pair_gross: dict[tuple[str, str], int],
    pair_cog: dict[tuple[str, str], int],
    span_inclusive_days: int,
    pair_units_with_cog: dict[tuple[str, str], int] | None = None,
    pair_units_with_cog_recent: dict[tuple[str, str], int] | None = None,
    cash_cycle_days: float = CASH_CYCLE_DAYS_DEFAULT,
    pair_buy_units_override: dict[tuple[str, str], float] | None = None,
) -> list[tuple[str, str, int, dict]]:
    rows: list[tuple[str, str, int, dict]] = []
    for k in keys:
        ac = pair_pool[k]
        if ac <= 0:
            continue
        buck, br = k
        if mode == "buy-plan":
            uov = None
            if pair_buy_units_override and k in pair_buy_units_override:
                v = pair_buy_units_override.get(k)
                if v is not None and float(v) > 0:
                    uov = float(v)
            m = layer2_row_buy_plan(
                allocated_cog_usd=ac / 100.0,
                recent_units_sold=int(pair_units_recent.get(k, 0)),
                recent_gross_cents=int(pair_gross_recent.get(k, 0)),
                recent_cog_cents=int(pair_cog_recent.get(k, 0)),
                velocity_span_inclusive_days=velocity_span,
                avg_units_per_day_override=(
                    float(pair_units_per_day_recent.get(k))
                    if pair_units_per_day_recent and k in pair_units_per_day_recent
                    else None
                ),
                units_from_allocation_override=uov,
                planner_score=planner_scores.get(k),
                cash_cycle_days=float(cash_cycle_days),
                cog_bearing_units=(
                    int(pair_units_with_cog_recent.get(k, 0))
                    if pair_units_with_cog_recent and k in pair_units_with_cog_recent
                    else None
                ),
            )
        else:
            m = layer2_row(
                allocated_cog_usd=ac / 100.0,
                units_sold=pair_units[k],
                gross_cents=pair_gross[k],
                cog_cents=pair_cog[k],
                span_inclusive_days=span_inclusive_days,
                cog_bearing_units=(
                    int(pair_units_with_cog.get(k, 0))
                    if pair_units_with_cog and k in pair_units_with_cog
                    else None
                ),
            )
        rows.append((br, buck, ac, m))
    rows.sort(key=lambda t: -t[2])
    return rows


def compare_allocation_modes_metrics(
    mode: str,
    rows: list[tuple[str, str, int, dict]],
) -> dict[str, Any]:
    """Aggregates for internal mode comparison (not SKU truth)."""
    total_rev = 0.0
    total_gp = 0.0
    for _, _, _ac, mm in rows:
        rv = mm.get("projected_revenue_from_allocated_units_usd")
        gp = mm.get("projected_gross_profit_usd")
        if rv is not None:
            total_rev += float(rv)
        if gp is not None:
            total_gp += float(gp)
    wn, wd = 0.0, 0.0
    if mode == "buy-plan":
        metric_key = "weeks_to_sell_through"
        recovery_label = "weighted_avg_weeks_to_sell_through"
    else:
        metric_key = "months_to_recover_cog"
        recovery_label = "weighted_avg_months_to_recover_cog"
    for _, _, ac, mm in rows:
        a_usd = ac / 100.0
        v = mm.get(metric_key)
        if v is not None and a_usd > 0:
            wn += float(v) * a_usd
            wd += a_usd
    wavg = wn / wd if wd > 0 else None
    return {
        "n_funded": len(rows),
        "recovery_label": recovery_label,
        "recovery_value": wavg,
        "total_rev": total_rev,
        "total_gp": total_gp,
    }


def render_allocation_compare_md(
    *,
    pool_cents: int,
    velocity_span: int,
    span_inclusive_days: int,
    min_cents: int,
    buy_plan_max_rows: int,
    min_upw: float,
    pool_top_n: int,
    cash_cycle_days: float,
    results: list[tuple[str, list[tuple[str, str, int, dict]], dict[str, Any]]],
) -> str:
    """Markdown artifact: three modes side by side on one data pull."""
    min_alloc_txt = "off (0)" if min_cents <= 0 else _usd(min_cents)
    lines: list[str] = [
        "# Allocation mode comparison (internal evaluation)",
        "",
        f"**Same order-item pull and pool** ({_usd(pool_cents)}). Compares how **buy-plan**, **throughput**, and "
        "**gross-share** deploy dollars across **brand × category** rows. **Projected revenue / GP** use each mode’s "
        "allocation × **trailing unit economics as modeled** — approximate, **not** validated SKU or pack-level truth.",
        "",
        "**Do not treat differences as proof of business optimality** — grouping and unit semantics are limited until "
        "schema validation (see `docs/GROWFLOW_PLANNER_DATA_MAPPING.md`).",
        "",
        "## Scenario knobs used for this comparison",
        "",
        f"- **buy-plan:** `velocity_window_days` = **{velocity_span}**, `cash_cycle_days` = **{cash_cycle_days:g}** "
        f"(max COG per row caps implied recovery at this many days), `min_units_per_week` = **{min_upw:g}**, "
        f"`buy_plan_max_rows` = **{buy_plan_max_rows}**, `min_allocated_usd` = **{min_alloc_txt}** (ignored for buy-plan cap logic).",
        f"- **throughput:** `pool_top_n` = **{pool_top_n if pool_top_n > 0 else 15}** (0 uses 15).",
        f"- **gross-share:** all cells with gross; full window **{span_inclusive_days}** days for layer2 trailing math.",
        "",
        "## Summary table",
        "",
        "| Mode | Funded rows | Weighted recovery | Total projected revenue | Total projected GP |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for mode, rows, met in results:
        rv = met["recovery_value"]
        rv_s = f"{rv:.2f}" if isinstance(rv, (int, float)) else "—"
        unit = "wks" if mode == "buy-plan" else "mo"
        lines.append(
            f"| `{mode}` | {met['n_funded']} | {rv_s} {unit} | {fmt_money(met['total_rev'])} | {fmt_money(met['total_gp'])} |"
        )
    lines.extend(
        [
            "",
            "**Weighted recovery:** **buy-plan** = weeks to sell through at recent velocity (by allocated COG $). "
            "**throughput** / **gross-share** = months to recover COG using the **full** trailing window "
            "(different semantics — compare directionally only).",
            "",
        ]
    )
    for mode, rows, met in results:
        lines.append(f"## Top 10 allocated rows — `{mode}`")
        lines.append("")
        rec_hdr = "Weeks to sell" if mode == "buy-plan" else "Mo recover"
        lines.append(f"| Rank | Brand | Category | Allocated COG $ | {rec_hdr} | Proj. revenue | Proj. GP |")
        lines.append("| ---: | --- | --- | ---: | ---: | ---: | ---: |")
        rec_key = "weeks_to_sell_through" if mode == "buy-plan" else "months_to_recover_cog"
        for i, (br, buck, ac, mm) in enumerate(rows[:10], start=1):
            rec = mm.get(rec_key)
            rec_s = f"{float(rec):.2f}" if rec is not None else "—"
            prv = mm.get("projected_revenue_from_allocated_units_usd")
            pgp = mm.get("projected_gross_profit_usd")
            lines.append(
                f"| {i} | {br} | {buck} | {_usd(ac)} | {rec_s} | "
                f"{fmt_money(float(prv) if prv is not None else None)} | "
                f"{fmt_money(float(pgp) if pgp is not None else None)} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("*Tool: `scripts/build_projection_by_category_brand.py --compare-modes`*")
    lines.append("")
    return "\n".join(lines)


def _fmt_float_cell(x: float | None, nd: int = 2) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return ""
    return format(x, f",.{nd}f")


def append_layer2_markdown(
    L,
    *,
    rows: list[tuple[str, str, int, dict]],
    pool_cents: int,
    span_inclusive_days: int,
    buy_plan: bool = False,
    velocity_days: int | None = None,
    cash_cycle_days: float = CASH_CYCLE_DAYS_DEFAULT,
    remaining_pool_unallocated_usd: float = 0.0,
) -> None:
    """Emit markdown: allocation, velocity/recovery, cash-cycle + demand detail, ranked lists."""
    sum_alloc_shown = sum(r[2] for r in rows)
    L("## Layer 2: velocity & COG recovery (required)")
    L("")
    if buy_plan and velocity_days:
        L(
            f"**Buy-plan mode (cash discipline):** Each funded line is **capped** so deployed COG ≤ **{cash_cycle_days:g} day(s)** "
            "of demand at **recent daily unit burn** (order-line count as units). "
            f"**cash_recovery_days** (= days to sell through this buy at that burn) should be **≤ {cash_cycle_days:g}** for "
            "**SAFE** capital. This is **not** on-hand inventory modeling — it is **cash recovery speed**."
        )
        L("")
        L(
            f"Recent velocity uses the last **{velocity_days}** store-local days (≈ **{velocity_days / 7.0:.1f} weeks**), "
            f"not the full **{span_inclusive_days}**-day pull used in gross tables above."
        )
        L("")
        L(
            "**Demand layer (time windows):** **units_needed_7d / 14d / 21d** and **cover_status** (URGENT / THIN / HEALTHY / HEAVY) "
            "describe how long the **planned buy** lasts vs 7–21 day needs at the same burn — parallel to the cash view."
        )
        L("")
        L(
            "**Grain:** Brand × format bucket — not SKU PO lines. **1 order line = 1 unit** until schema validates qty "
            "(see `unit_model_note` in CSV). `schema_validated=false` until SDL/playground."
        )
    else:
        L(
            f"Per **brand × category** cell: **allocated COG $** is the same projected pool $ as above; "
            f"**units** = counted order lines in the window (**1 line = 1 unit** in our API schema). "
            f"**Avg units/mo** annualizes over the **{span_inclusive_days}** store-local day window "
            f"(not a literal ÷12 unless the window is one calendar year). "
            f"**Avg COG/unit** uses summed line COG in the cell ÷ units (lines without usable COG reduce the average)."
        )
    L("")
    if sum_alloc_shown == pool_cents:
        L(f"**Check:** sum of **Allocated COG $** in §1 = **{_usd(pool_cents)}**.")
    elif buy_plan and remaining_pool_unallocated_usd > 0.005:
        L(
            f"**Check:** pool budget **{_usd(pool_cents)}**; **deployed** **{_usd(sum_alloc_shown)}**; "
            f"**unused (cash-cap / row limits):** **${remaining_pool_unallocated_usd:,.2f}** "
            f"(intentional when every eligible line hits its **{cash_cycle_days:g}-day** COG cap before the pool is spent)."
        )
    else:
        L(
            f"**Check:** pool **{_usd(pool_cents)}**; this section lists only cells with **> $0** allocated "
            f"(sum shown **{_usd(sum_alloc_shown)}**). Remaining cents are in **$0** cells, not shown."
        )
    L("")

    if buy_plan and rows:
        total_units = 0.0
        w_wk_n = 0.0
        w_wk_d = 0.0
        w_cash_n = 0.0
        w_cash_d = 0.0
        total_rev = 0.0
        total_gp = 0.0
        safe_usd = warn_usd = risk_usd = 0.0
        above14_usd = 0.0
        cap_hit = 0
        for _br, _bu, ac, mm in rows:
            a_usd = ac / 100.0
            u = mm.get("units_from_allocation")
            if u is not None:
                total_units += float(u)
            wk = mm.get("weeks_to_sell_through")
            if wk is not None and a_usd > 0:
                w_wk_n += float(wk) * a_usd
                w_wk_d += a_usd
            crd = mm.get("cash_recovery_days")
            if crd is not None and a_usd > 0:
                w_cash_n += float(crd) * a_usd
                w_cash_d += a_usd
            st_cc = mm.get("cash_cycle_status")
            if st_cc and a_usd > 0:
                if st_cc == "SAFE":
                    safe_usd += a_usd
                elif st_cc == "WARNING":
                    warn_usd += a_usd
                    above14_usd += a_usd
                elif st_cc == "CAPITAL RISK":
                    risk_usd += a_usd
                    above14_usd += a_usd
            rv = mm.get("projected_revenue_from_allocated_units_usd")
            gp = mm.get("projected_gross_profit_usd")
            if rv is not None:
                total_rev += float(rv)
            if gp is not None:
                total_gp += float(gp)
            if mm.get("capped_by_cash_cycle"):
                cap_hit += 1
        w_wk = w_wk_n / w_wk_d if w_wk_d > 0 else None
        w_cash = w_cash_n / w_cash_d if w_cash_d > 0 else None
        pool_usd = pool_cents / 100.0
        deployed_usd = sum_alloc_shown / 100.0
        top_scores = sorted(
            ((mm.get("planner_score") or 0, br, bu, mm) for br, bu, ac, mm in rows if ac > 0),
            key=lambda x: -x[0],
        )[:5]
        priority_gap = False
        for _sc, br, bu, mm in top_scores:
            crd = mm.get("cash_recovery_days")
            if crd is not None and float(crd) < 7.0:
                priority_gap = True
        urgent_cover: list[str] = []
        for br, bu, ac, mm in rows:
            if ac <= 0:
                continue
            if (mm.get("cover_status") or "") == "URGENT":
                urgent_cover.append(f"{br} / {bu}")
        L("### Buy plan summary (funded rows)")
        L("")
        L(f"- **Total units to purchase:** {total_units:,.2f}")
        L(
            f"- **Weighted avg cash_recovery_days:** {_fmt_float_cell(w_cash) if w_cash is not None else '—'} "
            f"(by allocated COG $). Allocator cap: **≤ {cash_cycle_days:g}** days at burn; **SAFE / WARNING / CAPITAL RISK** "
            "use fixed bands **≤14 / 14–21 / >21** days (see CSV `cash_cycle_status`)."
        )
        L(
            f"- **Weighted avg weeks sell-through (legacy):** {_fmt_float_cell(w_wk) if w_wk is not None else '—'} "
            "(same ratio as coverage_weeks; charts may still use this)."
        )
        if deployed_usd > 0:
            L(f"- **% deployed capital SAFE** (recovery ≤14 d, fixed band): **{100.0 * safe_usd / deployed_usd:.1f}%**")
            L(f"- **% deployed above 14 d** (WARNING + RISK): **{100.0 * above14_usd / deployed_usd:.1f}%**")
            L(
                f"- **% at CAPITAL RISK** (recovery >21 d): **{100.0 * risk_usd / deployed_usd:.1f}%** "
                f"(WARNING 14–21 d: **{100.0 * warn_usd / deployed_usd:.1f}%** of deployed)"
            )
        if pool_usd > 0 and remaining_pool_unallocated_usd > 0.005:
            L(
                f"- **Unused pool (not deployed):** **${remaining_pool_unallocated_usd:,.2f}** "
                f"({100.0 * remaining_pool_unallocated_usd / pool_usd:.1f}% of budget) — no remaining eligible row under cap."
            )
        L(f"- **Rows hitting cash-cycle cap:** **{cap_hit}**")
        L(f"- **Total projected revenue:** {fmt_money(total_rev)}")
        L(f"- **Total projected gross profit:** {fmt_money(total_gp)}")
        L("")
        L(f"### Cash-cycle & demand insights ({cash_cycle_days:g}-day recovery cap)")
        L("")
        L(
            "**Cash question:** *How fast does deployed COG come back at recent daily burn?* "
            "**Demand question:** *How long does this buy cover vs 7/14/21-day unit needs?*"
        )
        L("")
        if urgent_cover:
            L(
                "- **Cover URGENT** (<7 d at burn — stocking thin): "
                + ", ".join(urgent_cover[:10])
                + (" …" if len(urgent_cover) > 10 else "")
            )
        if priority_gap:
            L(
                "- **Check:** A **top-scored** line shows **< 7 days** recovery — unusual under cap; verify velocity window or data."
            )
        L("")

    L("### 1) Allocation table")
    L("")
    L("| Brand | Category | Allocated COG $ |")
    L("| --- | --- | ---: |")
    for br, buck, ac, _m in rows:
        L(f"| {br} | {buck} | {_usd(ac)} |")
    L("")

    L("### 2) Velocity / recovery table")
    L("")
    if buy_plan:
        L(
            "| Brand | Category | Allocated COG $ | Recent units | Avg units/wk | Avg COG/unit | "
            "Avg retail/unit | Units to purchase | Wks sell-through | Mo recover (equiv.) | "
            "Turns/yr | Recovery bucket | Proj. revenue | Proj. gross profit | Rev/$1 COG |"
        )
        L(
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"
        )
        for br, buck, ac, m in rows:
            L(
                f"| {br} | {buck} | {_usd(ac)} | {m['trailing_units_sold']:,} | "
                f"{_fmt_float_cell(m.get('avg_units_per_week'))} | "
                f"{fmt_money(m.get('avg_cog_per_unit'))} | "
                f"{fmt_money(m.get('avg_retail_per_unit'))} | "
                f"{_fmt_float_cell(m.get('units_from_allocation'))} | "
                f"{_fmt_float_cell(m.get('weeks_to_sell_through'))} | "
                f"{_fmt_float_cell(m.get('months_to_recover_cog'))} | "
                f"{_fmt_float_cell(m.get('turns_per_year'))} | "
                f"{m.get('recovery_bucket') or ''} | "
                f"{fmt_money(m.get('projected_revenue_from_allocated_units_usd'))} | "
                f"{fmt_money(m.get('projected_gross_profit_usd'))} | "
                f"{_fmt_float_cell(m.get('allocation_efficiency'), nd=3)} |"
            )
        L("")
        L(f"### 3) Cash + demand detail ({cash_cycle_days:g}-day COG cap)")
        L("")
        L(
            "| Brand | Category | Alloc COG $ | Avg u/day | Need 7d | Need 14d | Need 21d | "
            "Units buy | Days cover | Cash recv d | Max COG allow | @cap? | Cash status | Cover status |"
        )
        L("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |")
        for br, buck, ac, m in rows:
            cap_y = "**Y**" if m.get("capped_by_cash_cycle") else ""
            L(
                f"| {br} | {buck} | {_usd(ac)} | "
                f"{_fmt_float_cell(m.get('avg_units_per_day'))} | "
                f"{_fmt_float_cell(m.get('units_needed_7d'))} | "
                f"{_fmt_float_cell(m.get('units_needed_14d'))} | "
                f"{_fmt_float_cell(m.get('units_needed_21d'))} | "
                f"{_fmt_float_cell(m.get('units_from_allocation'))} | "
                f"{_fmt_float_cell(m.get('days_of_cover'))} | "
                f"{_fmt_float_cell(m.get('cash_recovery_days'))} | "
                f"{fmt_money(m.get('max_cog_allowed_usd'))} | {cap_y} | "
                f"{m.get('cash_cycle_status') or ''} | {m.get('cover_status') or ''} |"
            )
    else:
        L(
            "| Brand | Category | Allocated COG $ | Window units sold | Avg units/mo | "
            "Avg COG/unit | Avg retail/unit | Units from allocation | Months to recover COG | "
            "Turns/yr | Recovery bucket | Proj. revenue (alloc) | Proj. gross profit | Capital efficiency |"
        )
        L(
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |"
        )
        for br, buck, ac, m in rows:
            L(
                f"| {br} | {buck} | {_usd(ac)} | {m['trailing_units_sold']:,} | "
                f"{_fmt_float_cell(m.get('avg_units_per_month'))} | "
                f"{fmt_money(m.get('avg_cog_per_unit'))} | "
                f"{fmt_money(m.get('avg_retail_per_unit'))} | "
                f"{_fmt_float_cell(m.get('units_from_allocation'))} | "
                f"{_fmt_float_cell(m.get('months_to_recover_cog'))} | "
                f"{_fmt_float_cell(m.get('turns_per_year'))} | "
                f"{m.get('recovery_bucket') or ''} | "
                f"{fmt_money(m.get('projected_revenue_from_allocated_units_usd'))} | "
                f"{fmt_money(m.get('projected_gross_profit_usd'))} | "
                f"{_fmt_float_cell(m.get('allocation_efficiency'), nd=3)} |"
            )
    L("")

    def _payback_key(item: tuple[str, str, int, dict]) -> tuple:
        _br, _bu, _ac, mm = item
        mo = mm.get("months_to_recover_cog")
        if mo is None:
            return (1, float("inf"), _br.lower(), _bu)
        return (0, float(mo), _br.lower(), _bu)

    def _gp_key(item: tuple[str, str, int, dict]) -> tuple:
        _br, _bu, _ac, mm = item
        gp = mm.get("projected_gross_profit_usd")
        if gp is None:
            return (1, 0.0, _br.lower(), _bu)
        return (0, -float(gp), _br.lower(), _bu)

    def _eff_key(item: tuple[str, str, int, dict]) -> tuple:
        _br, _bu, _ac, mm = item
        ef = mm.get("allocation_efficiency")
        if ef is None:
            return (1, 0.0, _br.lower(), _bu)
        return (0, -float(ef), _br.lower(), _bu)

    L("### 4) Ranked buy recommendations")
    L("")
    L("**Fastest payback** (shortest months to recover allocated COG; rows with no velocity last).")
    L("")
    L("| Rank | Brand | Category | Months to recover | Allocated COG $ | Proj. gross profit |")
    L("| ---: | --- | --- | ---: | ---: | ---: |")
    for i, (br, buck, ac, mm) in enumerate(sorted(rows, key=_payback_key), start=1):
        L(
            f"| {i} | {br} | {buck} | {_fmt_float_cell(mm.get('months_to_recover_cog'))} | "
            f"{_usd(ac)} | {fmt_money(mm.get('projected_gross_profit_usd'))} |"
        )
    L("")
    L("**Highest projected gross profit** (from allocated units × avg retail − allocated COG).")
    L("")
    L("| Rank | Brand | Category | Proj. gross profit | Allocated COG $ | Months to recover |")
    L("| ---: | --- | --- | ---: | ---: | ---: |")
    for i, (br, buck, ac, mm) in enumerate(sorted(rows, key=_gp_key), start=1):
        L(
            f"| {i} | {br} | {buck} | {fmt_money(mm.get('projected_gross_profit_usd'))} | "
            f"{_usd(ac)} | {_fmt_float_cell(mm.get('months_to_recover_cog'))} |"
        )
    L("")
    L("**Highest capital efficiency** (projected revenue from allocated units ÷ allocated COG).")
    L("")
    L("| Rank | Brand | Category | Capital efficiency | Allocated COG $ | Months to recover |")
    L("| ---: | --- | --- | ---: | ---: | ---: |")
    for i, (br, buck, ac, mm) in enumerate(sorted(rows, key=_eff_key), start=1):
        L(
            f"| {i} | {br} | {buck} | {_fmt_float_cell(mm.get('allocation_efficiency'), nd=3)} | "
            f"{_usd(ac)} | {_fmt_float_cell(mm.get('months_to_recover_cog'))} |"
        )
    L("")


def append_what_buying_plan_does(
    L,
    *,
    pool_cents: int,
    velocity_span: int,
    min_upw: float,
    max_funded_rows: int,
    cash_cycle_days: float,
    remaining_pool_unallocated_usd: float,
    keys: list[tuple[str, str]],
    pair_pool: dict[tuple[str, str], int],
    layer2_rows: list[tuple[str, str, int, dict]],
    sku_first: bool = False,
) -> None:
    """Plain-English decision section for buy-plan mode (cash-cycle capped or SKU-first)."""
    funded = [k for k in keys if pair_pool.get(k, 0) > 0]
    n_funded = len(funded)
    top_share = 0.0
    if pool_cents > 0 and funded:
        biggest = max(funded, key=lambda k: pair_pool[k])
        top_share = 100.0 * pair_pool[biggest] / pool_cents
    slow_weeks = 0
    for _br, _bu, ac, mm in layer2_rows:
        w = mm.get("weeks_to_sell_through")
        if w is not None and float(w) > 6.0 and ac > 0:
            slow_weeks += 1
    L("## What this buying plan does")
    L("")
    if sku_first:
        L(
            f"- **Intent:** A **SKU-first reorder** deployment for **{_usd(pool_cents)}**: each funded "
            "**Product.objectId** line uses its own latest transfer receipt and sell-through since receipt; "
            "brand×category dollars are the **sum of SKU targets**, then the pool is **split in proportion** to those targets "
            "(still **not** a vendor PO line list until you map SKUs to packs)."
        )
        L(
            f"- **Recent demand:** Sell-through since receipt is measured from the receipt anchor through the last "
            f"**{velocity_span}** store-local days; a brand×category row must still average **≥ {min_upw:g}** units/week "
            "in that window to receive pool dollars."
        )
        L(
            f"- **Sizing:** Per-SKU targets use the same **{cash_cycle_days:g}-day** shelf horizon for fast sell-through "
            "as the buy-plan cash knob; slow movers do not shrink fast movers because math is **per product**, not blended."
        )
    else:
        L(
            f"- **Intent:** A **velocity-driven deployment** idea for **{_usd(pool_cents)}** — **not** a historical "
            "share-of-sales report and **not** exact SKU purchase orders. Inactive or low-velocity lines are filtered out "
            "and get **$0**."
        )
        L(
            f"- **Recent demand:** Velocity uses the last **{velocity_span}** store-local days only; "
            f"a line must average **≥ {min_upw:g}** units/week in that window (and have usable COG) to qualify."
        )
        L(
            f"- **Cash rule:** No line receives more COG than **{cash_cycle_days:g} day(s)** of sales at **recent daily** unit "
            "velocity. Allocator walks **score order** and assigns up to that cap per line until the **pool** or **candidates** "
            "run out. **No** extra pass piles dollars past the cap — leftover budget may stay **unallocated**."
        )
    if remaining_pool_unallocated_usd > 0.01:
        L(
            f"- **Unused pool this run:** **${remaining_pool_unallocated_usd:,.2f}** — all eligible lines hit their "
            f"**{cash_cycle_days:g}-day** COG ceiling before the full budget was placed."
        )
    if sku_first:
        L(
            f"- **Concentration:** At most **{max_funded_rows}** brand×category rows receive pool dollars, chosen by "
            f"**SKU-derived target COG** (highest targets first). **{n_funded}** lines received dollars this run."
        )
    else:
        L(
            f"- **Concentration:** At most **{max_funded_rows}** qualifying lines can receive funding; "
            f"ranked by score (weekly units, weekly COG $ pace, revenue per $1 COG). **{n_funded}** lines received "
            "dollars this run."
        )
    if top_share > 0:
        L(f"- **Largest single line** absorbs about **{top_share:.0f}%** of **deployed** dollars.")
    slow_cash = sum(
        1
        for _br, _bu, ac, mm in layer2_rows
        if ac > 0
        and mm.get("cash_recovery_days") is not None
        and float(mm["cash_recovery_days"]) > float(cash_cycle_days) + 0.5
    )
    if slow_cash > 0:
        L(
            f"- **Flag:** **{slow_cash}** funded line(s) show **cash_recovery_days** **>** **{cash_cycle_days:g}** — "
            "should not happen if caps bind; check data or rounding."
        )
    if slow_weeks > 0:
        L(
            f"- **Slow burn (legacy check):** **{slow_weeks}** line(s) need **> 6 weeks** to sell through **this entire buy** "
            f"at recent weekly pace (orthogonal to the **{cash_cycle_days:g}-day** cash cap)."
        )
    else:
        L(
            "- **Slow burn (legacy):** No funded line exceeds **6 weeks** to sell through this full buy at recent velocity."
        )
    L(
        "- **Excluded brands:** Same brand exclusions as the rest of the report (default: **(no brand)**, **Puffin Pure**, **710 Empire**, consignment vendors **Doc Furgsen** / **Doc Ferguson**, **Deadhead Farms**, **Arctic Extracts**, **Rooted Right Farms**); "
        "they do not receive pool dollars."
    )
    L("")


def write_layer2_csv(
    path: Path,
    rows: list[tuple[str, str, int, dict]],
    *,
    allocation_mode: str = "buy-plan",
    velocity_window_days_run: str = "",
    cash_cycle_days_run: str = "",
    remaining_pool_unallocated_usd: str = "",
    grouping_level: str = PLANNER_GROUPING_LEVEL,
    schema_validated: str = PLANNER_SCHEMA_VALIDATED,
    schema_source: str = PLANNER_SCHEMA_SOURCE,
    unit_model_note: str = PLANNER_UNIT_MODEL_NOTE,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "allocation_mode",
        "velocity_window_days_run",
        "cash_cycle_days_run",
        "remaining_pool_unallocated_usd",
        "grouping_level",
        "schema_validated",
        "schema_source",
        "unit_model_note",
        "brand",
        "category",
        "allocated_cog_usd",
        "trailing_units_sold",
        "velocity_window_days",
        "avg_units_per_week",
        "weeks_to_sell_through",
        "planner_score",
        "trailing_gross_usd",
        "trailing_cog_usd",
        "avg_units_per_month",
        "avg_cog_per_unit",
        "avg_retail_per_unit",
        "units_from_allocation",
        "months_to_recover_cog",
        "turns_per_year",
        "recovery_bucket",
        "projected_revenue_from_allocated_units_usd",
        "projected_gross_profit_usd",
        "allocation_efficiency",
        "avg_units_per_day",
        "days_of_inventory",
        "coverage_weeks",
        "units_needed_7d",
        "units_needed_14d",
        "units_needed_21d",
        "days_of_cover",
        "cover_status",
        "cash_recovery_days",
        "max_cog_allowed_usd",
        "capped_by_cash_cycle",
        "cash_cycle_status",
        # Full-run executive labels (duplicate on every row; same as Python → dashboard_data AC text KPIs)
        "exec_kpi_largest_allocation_label",
        "exec_kpi_fastest_recovery_label",
        "exec_kpi_highest_profit_label",
        "exec_kpi_best_efficiency_label",
        "exec_kpi_low_efficiency_high_dollar_label",
    ]
    kpi_row_dicts: list[dict[str, str]] = []
    body_rows: list[dict[str, Any]] = []
    for br, buck, ac, m in rows:
        capb = m.get("capped_by_cash_cycle")
        base = {
            "allocation_mode": allocation_mode,
            "velocity_window_days_run": velocity_window_days_run,
            "cash_cycle_days_run": cash_cycle_days_run,
            "remaining_pool_unallocated_usd": remaining_pool_unallocated_usd,
            "grouping_level": grouping_level,
            "schema_validated": schema_validated,
            "schema_source": schema_source,
            "unit_model_note": unit_model_note,
            "brand": br,
            "category": buck,
            "allocated_cog_usd": f"{ac / 100.0:.2f}",
            "trailing_units_sold": m["trailing_units_sold"],
            "velocity_window_days": m.get("velocity_window_days", ""),
            "avg_units_per_week": m.get("avg_units_per_week"),
            "weeks_to_sell_through": m.get("weeks_to_sell_through"),
            "planner_score": m.get("planner_score"),
            "trailing_gross_usd": m.get("trailing_gross_usd"),
            "trailing_cog_usd": m.get("trailing_cog_usd"),
            "avg_units_per_month": m.get("avg_units_per_month"),
            "avg_cog_per_unit": m.get("avg_cog_per_unit"),
            "avg_retail_per_unit": m.get("avg_retail_per_unit"),
            "units_from_allocation": m.get("units_from_allocation"),
            "months_to_recover_cog": m.get("months_to_recover_cog"),
            "turns_per_year": m.get("turns_per_year"),
            "recovery_bucket": m.get("recovery_bucket") or "",
            "projected_revenue_from_allocated_units_usd": m.get(
                "projected_revenue_from_allocated_units_usd"
            ),
            "projected_gross_profit_usd": m.get("projected_gross_profit_usd"),
            "allocation_efficiency": m.get("allocation_efficiency"),
            "avg_units_per_day": m.get("avg_units_per_day"),
            "days_of_inventory": m.get("days_of_inventory"),
            "coverage_weeks": m.get("coverage_weeks"),
            "units_needed_7d": m.get("units_needed_7d"),
            "units_needed_14d": m.get("units_needed_14d"),
            "units_needed_21d": m.get("units_needed_21d"),
            "days_of_cover": m.get("days_of_cover"),
            "cover_status": m.get("cover_status") or "",
            "cash_recovery_days": m.get("cash_recovery_days"),
            "max_cog_allowed_usd": m.get("max_cog_allowed_usd"),
            "capped_by_cash_cycle": (
                "true"
                if capb is True
                else ("false" if capb is False else "")
            ),
            "cash_cycle_status": m.get("cash_cycle_status") or "",
        }
        body_rows.append(base)
        kpi_row_dicts.append({k: ("" if v is None else str(v)) for k, v in base.items()})

    ex = compute_exec_kpis_for_csv(kpi_row_dicts)
    exec_snapshot = {
        "exec_kpi_largest_allocation_label": ex["largest_txt"],
        "exec_kpi_fastest_recovery_label": ex["fastest_major_txt"],
        "exec_kpi_highest_profit_label": ex["high_gp_txt"],
        "exec_kpi_best_efficiency_label": ex["hi_eff_txt"],
        "exec_kpi_low_efficiency_high_dollar_label": ex["lo_eff_txt"],
    }

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for base in body_rows:
            w.writerow({**base, **exec_snapshot})


def utc_bounds_for_store_local_days(
    store_tz,
    end_local: date,
    num_days: int,
) -> tuple[datetime, datetime]:
    """
    UTC range that covers inclusive store-local days
    [end_local - (num_days - 1), end_local].
    """
    if num_days < 1:
        raise ValueError("num_days must be >= 1")
    start_local = end_local - timedelta(days=num_days - 1)
    start_dt = datetime.combine(start_local, dt_time(0, 0, 0), tzinfo=store_tz)
    end_dt = datetime.combine(end_local, dt_time(23, 59, 59, 999999), tzinfo=store_tz)
    return start_dt.astimezone(timezone.utc), end_dt.astimezone(timezone.utc)


def num_biweek_periods(span_days_inclusive: int, period_days: int) -> int:
    if period_days < 1:
        raise ValueError("period_days must be >= 1")
    return (span_days_inclusive + period_days - 1) // period_days


def biweek_local_range(
    span_start: date,
    period_index: int,
    period_days: int,
    span_end: date,
) -> tuple[date, date]:
    a = span_start + timedelta(days=period_index * period_days)
    b = min(a + timedelta(days=period_days - 1), span_end)
    return a, b


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _load_config_flags() -> None:
    p = REPO / "config" / "config.yaml"
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        org = _yaml_scalar(text, "org_id")
        if org:
            os.environ["GROWFLOW_RETAIL_ORG"] = org


def _store_tz():
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = REPO / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    now = datetime.now().astimezone()
    return now.tzinfo or timezone.utc


def _credentials_path() -> str | None:
    p = (os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    if (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        return None
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def _usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _parse_min_units_overrides(raw_values: list[str]) -> dict[tuple[str, str], int]:
    """
    Parse repeated --min-units-override "Brand|Category|Units" args.
    """
    out: dict[tuple[str, str], int] = {}
    for raw in raw_values:
        s = str(raw or "").strip()
        if not s:
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) != 3:
            continue
        br, buck, units_s = parts
        if not br or not buck:
            continue
        try:
            u = int(float(units_s))
        except Exception:
            continue
        if u < 0:
            continue
        out[(buck, br)] = u
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Category x brand projection markdown (Growflow API)")
    ap.add_argument(
        "--days",
        type=int,
        default=365,
        help="Trailing **store-local** calendar days ending today (default 365 = ~12 months)",
    )
    ap.add_argument(
        "--biweek-days",
        type=int,
        default=14,
        help="Length of each leaderboard interval in store-local days (default 14)",
    )
    ap.add_argument(
        "--biweek-top",
        type=int,
        default=10,
        help="Top N brands per interval by focus-category gross (0 = skip section)",
    )
    ap.add_argument(
        "--max-brands-subprojection",
        type=int,
        default=0,
        help="Cap brands in 'By brand (sub-projection)' (0 = all brands with pool activity)",
    )
    ap.add_argument("--chunk-days", type=int, default=30, help="Days per API chunk")
    ap.add_argument("--pool", type=float, default=18_000.0, help="Total pool USD")
    ap.add_argument("--top-brands", type=int, default=10, help="Highlight top N brands by format gross")
    ap.add_argument("--max-rows-per-category", type=int, default=30, help="Max brand rows per category table")
    ap.add_argument("--out", type=Path, default=REPO / "data" / "projection_by_category_brand.md")
    ap.add_argument("--growflow-credentials", default=None)
    ap.add_argument(
        "--chunk-retries",
        type=int,
        default=5,
        help="Retries per chunk on network/API errors (default 5)",
    )
    ap.add_argument(
        "--exclude-brands",
        default=DEFAULT_EXCLUDE_BRANDS,
        help=(
            "Comma-separated brand labels excluded from pool split (case-insensitive). "
            "Default includes '(no brand)', Puffin Pure, 710 Empire, consignment brands "
            "(Doc Furgsen, Doc Ferguson, Deadhead Farms, Arctic Extracts, Rooted Right Farms). "
            "Use empty string to include all brands."
        ),
    )
    ap.add_argument(
        "--pool-top-n",
        type=int,
        default=15,
        help=(
            "**--allocation-mode throughput only:** full pool on top N brand×category cells by implied monthly COG "
            "throughput, split proportional to throughput. Use **0** with **gross-share** mode for all cells. "
            "Ignored for **buy-plan** (use --buy-plan-max-rows instead)."
        ),
    )
    ap.add_argument(
        "--no-layer2",
        action="store_true",
        help="Skip second-layer recovery / velocity tables and CSV",
    )
    ap.add_argument(
        "--layer2-csv",
        type=Path,
        default=None,
        help="Write layer-2 metrics CSV (default: same stem as --out with _layer2_recovery.csv)",
    )
    ap.add_argument(
        "--allocation-mode",
        choices=("buy-plan", "throughput", "gross-share"),
        default="buy-plan",
        help=(
            "buy-plan: recent-velocity ranked deployment (default). throughput: legacy top-N monthly COG pace. "
            "gross-share: split pool across all cells by trailing gross."
        ),
    )
    ap.add_argument(
        "--velocity-days",
        type=int,
        default=49,
        help="Buy-plan: store-local days for recent velocity (default 49 ≈ 7 weeks); capped by --days.",
    )
    ap.add_argument(
        "--velocity-anchor",
        choices=("window-start", "receipt-aware"),
        default="window-start",
        help=(
            "How buy-plan velocity starts per product. "
            "window-start = legacy behavior (same trailing window for all rows). "
            "receipt-aware = per product, velocity starts at max(window-start, latest transfer receipt date)."
        ),
    )
    ap.add_argument(
        "--cycle-growth-sensitivity",
        type=float,
        default=0.50,
        help="Receipt-aware cycle model: fraction of sell-through overage applied as growth to next receipt units.",
    )
    ap.add_argument(
        "--cycle-shrink-sensitivity",
        type=float,
        default=0.60,
        help="Receipt-aware cycle model: fraction of under-sell applied as reduction to next receipt units.",
    )
    ap.add_argument(
        "--cycle-discontinue-ratio",
        type=float,
        default=0.30,
        help="Receipt-aware cycle model: if sold/receipt <= this ratio, recommendation can drop to 0 (discontinue).",
    )
    ap.add_argument(
        "--min-units-per-week",
        type=float,
        default=3.0,
        help="Buy-plan hard filter: min avg units/week in the velocity window.",
    )
    ap.add_argument(
        "--buy-plan-max-rows",
        type=int,
        default=20,
        help="Buy-plan: max brand×category rows that receive any pool dollars (ranked by score).",
    )
    ap.add_argument(
        "--min-allocated-usd",
        type=float,
        default=50.0,
        help="Buy-plan: **ignored** for cash-cycle allocation (capping would break the 14-day rule). Other modes: unchanged.",
    )
    ap.add_argument(
        "--cash-cycle-days",
        type=float,
        default=CASH_CYCLE_DAYS_DEFAULT,
        help="Buy-plan: max COG per row = this many days of demand at recent daily burn (default 14).",
    )
    ap.add_argument(
        "--transfer-receipts-db",
        type=Path,
        default=REPO / "data" / "transfer_receipts.db",
        help="SQLite DB path from scripts/build_transfer_receipts_db.py (for landed unit cost by Product.objectId).",
    )
    ap.add_argument(
        "--landed-cog",
        choices=("off", "auto", "prefer"),
        default="auto",
        help=(
            "How to apply transfer-landed unit costs when available. "
            "off = use order-line COG only; prefer = use landed unit cost when found, else line COG; "
            "auto = prefer if transfer DB + product_landed_cost_current exist."
        ),
    )
    ap.add_argument(
        "--compare-modes",
        action="store_true",
        help=(
            "After the main run, write a second markdown file comparing buy-plan vs throughput vs gross-share "
            "on the same pulled data (internal evaluation only; see docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md)."
        ),
    )
    ap.add_argument(
        "--compare-modes-out",
        type=Path,
        default=None,
        help="Output path for --compare-modes (default: <stem>_allocation_compare.md next to --out).",
    )
    ap.add_argument(
        "--validation-mode",
        choices=("strict", "warning", "discovery"),
        default="strict",
        help="Validation gateway mode (strict fail-closed by default).",
    )
    ap.add_argument(
        "--min-units-override",
        action="append",
        default=[],
        help=(
            "Repeatable floor override for buy-plan cycle targets at brand/category grain. "
            "Format: 'Brand|Category|Units' (example: \"Stoner's Extracts|Disposables|100\")."
        ),
    )
    args = ap.parse_args()

    _load_config_flags()
    tz = _store_tz()
    creds = args.growflow_credentials or _credentials_path()
    pool_cents = int(round(float(args.pool) * 100.0))
    excluded_cf = parse_brand_exclusions(args.exclude_brands)
    min_units_override = _parse_min_units_overrides(list(args.min_units_override or []))

    report_end_local = datetime.now(tz).date()
    report_start_local = report_end_local - timedelta(days=args.days - 1)
    span_inclusive_days = (report_end_local - report_start_local).days + 1
    window_start, window_end = utc_bounds_for_store_local_days(tz, report_end_local, args.days)

    velocity_span = min(int(args.velocity_days), int(args.days))
    if int(args.velocity_days) > int(args.days):
        print(
            f"NOTE: --velocity-days {args.velocity_days} capped to --days {args.days}.",
            flush=True,
        )
    recent_start_local = report_end_local - timedelta(days=velocity_span - 1)
    pair_units_recent: dict[tuple[str, str], int] = defaultdict(int)
    pair_units_with_cog_recent: dict[tuple[str, str], int] = defaultdict(int)
    pair_gross_recent: dict[tuple[str, str], int] = defaultdict(int)
    pair_cog_recent: dict[tuple[str, str], int] = defaultdict(int)
    pair_units_per_day_recent: dict[tuple[str, str], float] = defaultdict(float)

    landed_unit_cost: dict[str, int] = {}
    latest_receipt_snapshot: dict[str, dict[str, Any]] = {}
    landed_mode = str(args.landed_cog or "auto").strip().lower()
    if landed_mode not in ("off", "auto", "prefer"):
        landed_mode = "auto"
    if landed_mode != "off":
        # auto: only enable if DB exists and the table is readable
        latest_receipt_snapshot = _load_latest_receipt_snapshot_by_product_object_id(Path(args.transfer_receipts_db))
        landed_unit_cost = {
            pid: int(v["unit_cost_cents"])
            for pid, v in latest_receipt_snapshot.items()
            if isinstance(v.get("unit_cost_cents"), int)
        }
        if landed_mode == "auto" and not landed_unit_cost:
            landed_mode = "off"
    landed_overrides = 0
    landed_seen = 0
    latest_received_by_product: dict[str, datetime] = {}
    velocity_anchor_effective = str(args.velocity_anchor)
    if str(args.velocity_anchor) == "receipt-aware":
        if not latest_receipt_snapshot:
            latest_receipt_snapshot = _load_latest_receipt_snapshot_by_product_object_id(Path(args.transfer_receipts_db))
        latest_received_by_product = {
            pid: v["received_at"]
            for pid, v in latest_receipt_snapshot.items()
            if isinstance(v.get("received_at"), datetime)
        }
        if not latest_received_by_product:
            velocity_anchor_effective = "window-start"
            print(
                "NOTE: --velocity-anchor receipt-aware requested, but no transfer receipt anchors found; "
                "falling back to window-start.",
                flush=True,
            )
    # For receipt-aware mode, compute per-(bucket,brand,product) units and denominators.
    prod_units_recent: dict[tuple[tuple[str, str], str], int] = defaultdict(int)
    prod_den_days_recent: dict[tuple[tuple[str, str], str], int] = {}
    prod_units_since_receipt: dict[tuple[tuple[str, str], str], int] = defaultdict(int)
    pair_cycle_unit_cost_samples: dict[tuple[str, str], list[int]] = defaultdict(list)

    oi_query = ORDER_ITEMS_QUERY
    seen: set[str] = set()
    # (bucket, brand) -> gross cents (format buckets only)
    pair_gross: dict[tuple[str, str], int] = defaultdict(int)
    # One unit per order line (API has no line quantity in our queries).
    pair_units: dict[tuple[str, str], int] = defaultdict(int)
    pair_units_with_cog: dict[tuple[str, str], int] = defaultdict(int)
    pair_cog: dict[tuple[str, str], int] = defaultdict(int)
    other_gross = 0
    excluded_focus_gross = 0  # excluded brands, bucket != Other (not in pool denominator)
    excluded_other_gross = 0  # excluded brands in Growflow "Other" category
    # biweek_idx -> brand -> gross cents (same rules as pair_gross)
    biweek_by_brand: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    chunk_idx = 0
    validation_rows: list[dict[str, Any]] = []

    for from_iso, to_iso in iter_sold_at_date_chunks(window_start, window_end, args.chunk_days):
        chunk_idx += 1
        where = date_range_to_where("SoldAt", from_iso, to_iso)
        raw, oi_query = _fetch_chunk(
            oi_query=oi_query,
            where=where,
            creds=creds,
            chunk_idx=chunk_idx,
            retries=args.chunk_retries,
        )

        for n, ld in _unique_order_items_in_local_window(raw, seen, tz, report_start_local, report_end_local):
            validation_rows.append(n)

            bucket = order_line_format_bucket(n)
            b = brand_label_from_line(n)
            gp = cents_field(n.get("GrossPrice"))
            excl = brand_excluded(b, excluded_cf)

            if bucket == "Other":
                if excl:
                    excluded_other_gross += gp
                else:
                    other_gross += gp
                continue

            if excl:
                excluded_focus_gross += gp
                continue

            # TODO(schema truth): Stable product/SKU key would join validated findProducts / line qty when available
            # (docs/GROWFLOW_PLANNER_DATA_MAPPING.md). Today: aggregate by inferred format bucket × brand string.
            key_bc = (bucket, b)
            pair_gross[key_bc] += gp
            pair_units[key_bc] += 1
            # Base: order-line COG (may be missing or invalid).
            cog_line = usable_cog_cents(gp, n.get("COG"))
            # Optional override: transfer-landed unit cost keyed by Product.objectId.
            if landed_mode != "off":
                prod = n.get("Product") if isinstance(n.get("Product"), dict) else {}
                pid = str(prod.get("objectId") or "").strip()
                if pid:
                    landed_seen += 1
                    ucc = landed_unit_cost.get(pid)
                    if isinstance(ucc, int) and ucc >= 0:
                        cog_line = int(ucc)
                        landed_overrides += 1
            pair_cog[key_bc] += cog_line
            if cog_line > 0:
                pair_units_with_cog[key_bc] += 1
            include_recent = False
            if velocity_anchor_effective == "receipt-aware":
                prod = n.get("Product") if isinstance(n.get("Product"), dict) else {}
                pid = str(prod.get("objectId") or "").strip() or "(no_product_id)"
                anchor_local = recent_start_local
                recv_dt = latest_received_by_product.get(pid)
                if recv_dt is not None:
                    recv_local = recv_dt.astimezone(tz).date()
                    if recv_local > anchor_local:
                        anchor_local = recv_local
                if ld >= anchor_local:
                    include_recent = True
                    pkey = (key_bc, pid)
                    prod_units_recent[pkey] += 1
                    prod_units_since_receipt[pkey] += 1
                    snap = latest_receipt_snapshot.get(pid) if latest_receipt_snapshot else None
                    if isinstance(snap, dict) and isinstance(snap.get("unit_cost_cents"), int):
                        pair_cycle_unit_cost_samples[key_bc].append(int(snap["unit_cost_cents"]))
                    if pkey not in prod_den_days_recent:
                        den = (report_end_local - anchor_local).days + 1
                        prod_den_days_recent[pkey] = max(1, den)
            else:
                include_recent = ld >= recent_start_local

            if include_recent:
                pair_units_recent[key_bc] += 1
                pair_gross_recent[key_bc] += gp
                pair_cog_recent[key_bc] += cog_line
                if cog_line > 0:
                    pair_units_with_cog_recent[key_bc] += 1
            off = (ld - report_start_local).days
            bidx = off // max(1, args.biweek_days)
            biweek_by_brand[bidx][b] += gp

    total_fmt = sum(pair_gross.values())
    if velocity_anchor_effective == "receipt-aware":
        # Sum product-level per-day rates into each brand×bucket row.
        for (key_bc, _pid), units in prod_units_recent.items():
            den = int(prod_den_days_recent.get((key_bc, _pid), max(1, velocity_span)))
            pair_units_per_day_recent[key_bc] += float(units) / float(max(1, den))
    else:
        for k, u in pair_units_recent.items():
            pair_units_per_day_recent[k] = float(u) / float(max(1, velocity_span))
    pair_sku_pre_cents: dict[tuple[str, str], int] = {}
    pair_sku_pre_units: dict[tuple[str, str], int] = {}
    if args.allocation_mode == "buy-plan" and velocity_anchor_effective == "receipt-aware" and latest_receipt_snapshot:
        pair_sku_pre_cents, pair_sku_pre_units = build_sku_pre_scale_buy(
            prod_units_since_receipt=prod_units_since_receipt,
            prod_den_days_recent=prod_den_days_recent,
            latest_receipt_snapshot=latest_receipt_snapshot,
            velocity_span=velocity_span,
            growth_sensitivity=float(args.cycle_growth_sensitivity),
            shrink_sensitivity=float(args.cycle_shrink_sensitivity),
            discontinue_ratio=float(args.cycle_discontinue_ratio),
            shelf_days=float(args.cash_cycle_days),
            on_hand_by_product_id=None,
        )
        if min_units_override:
            for k, min_u in min_units_override.items():
                pu = int(pair_sku_pre_units.get(k, 0))
                pc = int(pair_sku_pre_cents.get(k, 0))
                avg_uc = pc // pu if pu > 0 else 0
                need = max(0, int(min_u) - pu)
                if need > 0 and avg_uc > 0:
                    pair_sku_pre_units[k] = pu + need
                    pair_sku_pre_cents[k] = pc + need * int(avg_uc)

    pair_cycle_target_units: dict[tuple[str, str], float] = {}
    pair_cycle_unit_cost_cents: dict[tuple[str, str], int] = {}
    _sku_pre_total = sum(int(pair_sku_pre_cents.get(k, 0)) for k in pair_sku_pre_cents) if pair_sku_pre_cents else 0
    if (
        args.allocation_mode == "buy-plan"
        and velocity_anchor_effective == "receipt-aware"
        and _sku_pre_total <= 0
    ):
        for (key_bc, pid), sold_u in prod_units_since_receipt.items():
            snap = latest_receipt_snapshot.get(pid) if latest_receipt_snapshot else None
            receipt_qty = int(snap.get("original_qty")) if isinstance(snap, dict) and snap.get("original_qty") else None
            if receipt_qty is None or receipt_qty <= 0:
                pair_cycle_target_units[key_bc] = pair_cycle_target_units.get(key_bc, 0.0) + float(max(0, sold_u))
                continue
            ratio = float(sold_u) / float(receipt_qty)
            if ratio <= float(args.cycle_discontinue_ratio):
                target_u = 0.0
            elif ratio >= 1.0:
                growth = 1.0 + float(args.cycle_growth_sensitivity) * (ratio - 1.0)
                target_u = float(receipt_qty) * growth
            else:
                shrink = 1.0 - float(args.cycle_shrink_sensitivity) * (1.0 - ratio)
                target_u = float(receipt_qty) * max(0.0, shrink)
            if ratio >= 0.95:
                den_days = int(prod_den_days_recent.get((key_bc, pid), max(1, velocity_span)))
                daily_prod = float(sold_u) / float(max(1, den_days))
                demand_target = daily_prod * float(args.cash_cycle_days)
                if demand_target > target_u:
                    target_u = demand_target
            pair_cycle_target_units[key_bc] = pair_cycle_target_units.get(key_bc, 0.0) + max(0.0, float(target_u))
        for k, vals in pair_cycle_unit_cost_samples.items():
            if not vals:
                continue
            try:
                pair_cycle_unit_cost_cents[k] = int(round(float(median(vals))))
            except Exception:
                continue
        if min_units_override:
            for k, min_u in min_units_override.items():
                curr = float(pair_cycle_target_units.get(k, 0.0))
                if float(min_u) > curr:
                    pair_cycle_target_units[k] = float(min_u)
    validation = validate_and_normalize(
        metric_id="projection_by_category_brand",
        template_id="order_items_projection_buy_plan_v1",
        raw_json={"data": {"findOrderItems": {"edges": [{"node": r} for r in validation_rows]}}},
        request_context={
            "requested_date_range": {
                "from": window_start.isoformat().replace("+00:00", "Z"),
                "to": window_end.isoformat().replace("+00:00", "Z"),
            },
            "source_script": "scripts/build_projection_by_category_brand.py",
            "allocation_mode": args.allocation_mode,
        },
        mode=args.validation_mode,
    )
    print(f"Validation report: {validation.get('report_path')}", flush=True)
    if not validation.get("ok"):
        print(f"Validation blocked trusted output: {validation.get('errors')}", flush=True)
        return 1
    if total_fmt <= 0:
        print("No sales in focus categories in this window; cannot build projection.", flush=True)
        return 1

    # Stable ordering: bucket order then brand name
    def sort_key(item: tuple[tuple[str, str], int]) -> tuple:
        (buck, br), _ = item
        try:
            bi = BUCKET_DISPLAY_ORDER.index(buck)
        except ValueError:
            bi = 99
        return (bi, br.lower())

    sorted_pairs = sorted(pair_gross.items(), key=sort_key)
    keys = [p[0] for p in sorted_pairs]
    min_cents = (
        int(round(float(args.min_allocated_usd) * 100.0))
        if float(args.min_allocated_usd) > 0
        else 0
    )
    pair_pool, planner_scores = allocate_for_mode(
        args.allocation_mode,
        pool_cents,
        keys,
        pair_gross,
        pair_units,
        pair_cog,
        span_inclusive_days,
        total_fmt,
        pair_units_recent,
        pair_gross_recent,
        pair_cog_recent,
        velocity_span,
        pair_units_with_cog=pair_units_with_cog,
        pair_units_with_cog_recent=pair_units_with_cog_recent,
        pair_units_per_day_recent=pair_units_per_day_recent,
        pair_cycle_target_units=pair_cycle_target_units,
        pair_cycle_unit_cost_cents=pair_cycle_unit_cost_cents,
        sku_pre_scale_cents=pair_sku_pre_cents,
        min_units_per_week=float(args.min_units_per_week),
        buy_plan_max_rows=max(1, int(args.buy_plan_max_rows)),
        min_allocated_cents=min_cents,
        pool_top_n=int(args.pool_top_n),
        cash_cycle_days=float(args.cash_cycle_days),
    )
    alloc = [pair_pool[k] for k in keys]
    sum_alloc_cents = sum(alloc)
    if args.allocation_mode == "buy-plan":
        issues: list[str] = []
        if any(a < 0 for a in alloc):
            issues.append("NEGATIVE_ALLOCATION")
        if sum_alloc_cents > pool_cents:
            issues.append(f"SUM_EXCEEDS_POOL: {sum_alloc_cents} > {pool_cents}")
    else:
        issues = validate_allocation(pool_cents, alloc)
    if issues:
        if args.allocation_mode == "buy-plan" and sum(alloc) == 0:
            print(
                "ERROR: buy-plan filters left no qualifying rows for the pool "
                "(try lowering --min-units-per-week, widening --velocity-days, or use --allocation-mode throughput).",
                flush=True,
            )
            return 1
        print("WARNING:", issues, flush=True)

    pair_buy_units_override: dict[tuple[str, str], float] = {}
    if pair_sku_pre_cents and sum(int(pair_sku_pre_cents.get(k, 0)) for k in keys) > 0:
        for k in keys:
            ac = int(pair_pool.get(k, 0))
            pu = int(pair_sku_pre_units.get(k, 0))
            pc = int(pair_sku_pre_cents.get(k, 0))
            if ac > 0 and pu > 0 and pc > 0:
                pair_buy_units_override[k] = float(ac) * float(pu) / float(pc)

    buy_plan_sku_first_active = (
        args.allocation_mode == "buy-plan"
        and velocity_anchor_effective == "receipt-aware"
        and bool(pair_sku_pre_cents)
        and sum(int(pair_sku_pre_cents.get(k, 0)) for k in pair_sku_pre_cents) > 0
    )

    layer2_rows: list[tuple[str, str, int, dict]] = []
    if not args.no_layer2:
        layer2_rows = build_layer2_rows_list(
            args.allocation_mode,
            keys,
            pair_pool,
            planner_scores,
            pair_units_recent,
            pair_gross_recent,
            pair_cog_recent,
            velocity_span,
            pair_units_per_day_recent,
            pair_units,
            pair_gross,
            pair_cog,
            span_inclusive_days,
            pair_units_with_cog=pair_units_with_cog,
            pair_units_with_cog_recent=pair_units_with_cog_recent,
            cash_cycle_days=float(args.cash_cycle_days),
            pair_buy_units_override=pair_buy_units_override or None,
        )

    remaining_pool_unallocated_usd = max(0.0, (pool_cents - sum_alloc_cents) / 100.0)

    brand_gross_fmt: dict[str, int] = defaultdict(int)
    brand_pool_fmt: dict[str, int] = defaultdict(int)
    for (buck, br), g in pair_gross.items():
        brand_gross_fmt[br] += g
        brand_pool_fmt[br] += pair_pool[(buck, br)]

    top_n = sorted(brand_gross_fmt.keys(), key=lambda br: -brand_gross_fmt[br])[: max(1, args.top_brands)]

    bucket_gross: dict[str, int] = defaultdict(int)
    bucket_pool: dict[str, int] = defaultdict(int)
    for (buck, br), g in pair_gross.items():
        bucket_gross[buck] += g
        bucket_pool[buck] += pair_pool[(buck, br)]

    by_brand_cats: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for (buck, br), g in pair_gross.items():
        if g <= 0:
            continue
        by_brand_cats[br].append((buck, g, pair_pool[(buck, br)]))

    cap = args.max_brands_subprojection
    brand_order_sub = sorted(
        by_brand_cats.keys(),
        key=lambda b: (-brand_pool_fmt[b], -brand_gross_fmt[b], b.lower()),
    )
    if cap > 0:
        brand_order_sub = brand_order_sub[:cap]

    lines_out: list[str] = []
    L = lines_out.append

    L("# Brand pool projection (by category and brand)")
    L("")
    L(
        "> **What this is:** A **velocity-grounded** capital deployment view at **brand × category** grain, "
        "from **recent sales behavior** (when using buy-plan). **Not** exact **SKU purchase instructions** or pack-level "
        "truth. **Planning metadata** (below) and `docs/GROWFLOW_PLANNER_SCENARIO_CONTROLS.md` document limits and knobs."
    )
    L("")
    L("## Summary")
    L("")
    L(f"- **Generated:** {datetime.now(tz).strftime('%Y-%m-%d %H:%M')} store-local ({getattr(tz, 'key', None) or tz})")
    L(
        f"- **Sales window:** last **{args.days}** **store-local** calendar days "
        f"**{report_start_local.isoformat()}** through **{report_end_local.isoformat()}** (inclusive); "
        f"API `SoldAt` range is the matching UTC span, chunked fetch"
    )
    L(f"- **Pool:** **{_usd(pool_cents)}** total")
    L(f"- **Allocation mode:** **{args.allocation_mode}**")
    if args.allocation_mode == "buy-plan":
        if buy_plan_sku_first_active:
            L(
                f"- **Buy plan (SKU-first, receipt-aware):** reorder targets are built **per Product.objectId** from "
                f"latest transfer receipt + sell-through since receipt (fast SKUs not averaged with slow siblings); "
                f"the **{_usd(pool_cents)}** pool is split **in proportion to those SKU-derived COG targets** among "
                f"eligible brand×category rows (min **{float(args.min_units_per_week):g}** units/week; top **{int(args.buy_plan_max_rows)}** by target). "
                f"**Deployed:** **{_usd(sum_alloc_cents)}**; **unused:** **${remaining_pool_unallocated_usd:,.2f}**."
            )
        else:
            L(
                f"- **Buy plan (cash cycle):** **≤ {float(args.cash_cycle_days):g} day(s)** COG recovery per line at recent daily burn; "
                f"score-ranked fill until pool or caps exhausted. Recent velocity = last **{velocity_span}** days (~**{velocity_span / 7.0:.1f} wks**); "
                f"require **≥ {float(args.min_units_per_week):g}** avg units/week; **≤ {int(args.buy_plan_max_rows)}** candidate lines. "
                f"**Deployed:** **{_usd(sum_alloc_cents)}**; **unused:** **${remaining_pool_unallocated_usd:,.2f}** if caps bind first."
            )
    elif args.allocation_mode == "throughput":
        n_top = int(args.pool_top_n) if int(args.pool_top_n) > 0 else 15
        L(
            f"- **Throughput mode:** top **{n_top}** cells by implied monthly COG throughput; "
            "pool split proportional to throughput among those cells; others **$0**."
        )
    else:
        L("- **Gross-share mode:** pool split across **all** cells by trailing gross share.")
    if not args.no_layer2:
        L(
            "- **Layer 2:** Buy/velocity metrics and ranked lists (below); CSV `*_layer2_recovery.csv`. "
            "Pass `--no-layer2` to omit."
        )
    L(f"- **Unique order lines counted:** {len(validation_rows):,}")
    if excluded_cf:
        shown = ", ".join(sorted({s for s in (args.exclude_brands or "").split(",") if s.strip()}))
        L(f"- **Brands excluded from pool split:** {shown}")
        L(
            f"- **Excluded brands' gross (focus categories only):** {_usd(excluded_focus_gross)} "
            f"(not in the proportional split)"
        )
        if excluded_other_gross:
            L(f"- **Excluded brands' gross (Growflow Other category):** {_usd(excluded_other_gross)}")
    L(
        f"- **Sales in focus categories (pool-eligible):** {_usd(total_fmt)} gross; "
        f"**Growflow Other category (pool-eligible brands):** {_usd(other_gross)}"
    )
    denom_all = total_fmt + other_gross + excluded_focus_gross + excluded_other_gross
    if denom_all > 0:
        L(
            f"- **Context:** pool-eligible focus gross is {100.0 * total_fmt / denom_all:.1f}% of "
            f"focus+Other gross on counted lines (including excluded-brand lines)."
        )
    L("")
    L("### Planning metadata")
    L("")
    L(f"- **allocation_mode:** `{args.allocation_mode}`")
    L(
        f"- **velocity_window_days:** "
        f"`{velocity_span}` — **buy-plan** uses this window for velocity, scoring, and sell-through; "
        f"gross tables still use the full **{span_inclusive_days}**-day pull."
        if args.allocation_mode == "buy-plan"
        else f"`—` (not used for allocation ranking); **layer2** trailing metrics use the full **{span_inclusive_days}**-day window"
    )
    L(f"- **grouping_level:** `{PLANNER_GROUPING_LEVEL}` (brand × format bucket — not SKU-level)")
    L(f"- **schema_validated:** `{PLANNER_SCHEMA_VALIDATED}` (production GraphQL introspection blocked; no SDL-backed join yet)")
    L(f"- **schema_source:** `{PLANNER_SCHEMA_SOURCE}` (see `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md`)")
    L(f"- **unit_model_note:** `{PLANNER_UNIT_MODEL_NOTE}`")
    if landed_mode != "off":
        L(
            f"- **landed_cog:** `{args.landed_cog}` — using transfer receipts DB "
            f"`{Path(args.transfer_receipts_db).as_posix()}` when available "
            f"(overrode **{landed_overrides}** of **{landed_seen}** eligible order lines with "
            "unit cost from latest Accepted transfer)."
        )
    if args.allocation_mode == "buy-plan":
        L(f"- **cash_cycle_days:** `{float(args.cash_cycle_days):g}` (max COG per row = this many days of demand at daily burn)")
    L(
        f"- **velocity_window_days_run (CSV column):** `{velocity_span}` for **buy-plan** (recent velocity); "
        f"`{span_inclusive_days}` for **throughput** / **gross-share** (full `--days` window underlying layer2 trailing metrics)."
    )
    if args.allocation_mode == "buy-plan":
        L(
            f"- **velocity_anchor:** `{velocity_anchor_effective}` "
            "(receipt-aware uses max(window-start, latest transfer receipt date per Product.objectId))."
        )
        L(
            f"- **buy_plan_engine:** `{'sku_pre_scale' if buy_plan_sku_first_active else 'score_capped_velocity'}` "
            "(SKU-first uses `lib/projection_sku_reorder.py` when receipt data + sell-through produce non-zero targets)."
        )
    L("")
    L(
        "**Caveats:** Product/category/brand accuracy is limited to order-line and title-inference rules until "
        "`findProducts` / `findProductCategories` / `findBrands` are validated. Units ≈ order-line count (not pack qty). "
        "Receipt-aware SKU costs come from the transfer receipts SQLite DB when enabled; optional `findPackages` on-hand "
        "feeds for shelf-out boosts are not wired in this script yet — see `docs/GROWFLOW_PLANNER_DATA_MAPPING.md`."
    )
    L("")
    if args.allocation_mode == "buy-plan" and layer2_rows:
        append_what_buying_plan_does(
            L,
            pool_cents=pool_cents,
            velocity_span=velocity_span,
            min_upw=float(args.min_units_per_week),
            max_funded_rows=max(1, int(args.buy_plan_max_rows)),
            cash_cycle_days=float(args.cash_cycle_days),
            remaining_pool_unallocated_usd=remaining_pool_unallocated_usd,
            keys=keys,
            pair_pool=pair_pool,
            layer2_rows=layer2_rows,
            sku_first=buy_plan_sku_first_active,
        )
    L("## How to read this")
    L("")
    L(
        (
            "Dollars in the **Projected pool** column are your share of the fixed **"
            f"{_usd(pool_cents)}** budget. "
            + (
                "In **buy-plan** mode, dollars deploy under a **cash-cycle cap** (default **14 days** of COG at recent daily burn); "
                "the full budget may be **partially unused**. Layer 2 reports **cash_recovery_days**, demand windows (7/14/21 d), "
                "and **not** SKU-level PO truth. "
                if args.allocation_mode == "buy-plan"
                else (
                    f"When **`throughput`** mode is used with top-N cells, only those lines receive pool dollars. "
                    if args.allocation_mode == "throughput"
                    else "This is **in proportion to gross sales** in each **product category × brand** cell over the window. "
                )
            )
        )
        + "It is a planning split, not COGS. "
        "Named brands can be excluded from the split (default: **(no brand)**, **Puffin Pure**, **710 Empire**, "
        "consignment: **Doc Furgsen**/**Doc Ferguson**, **Deadhead Farms**, **Arctic Extracts**, **Rooted Right Farms**); "
        "the full **"
        f"{_usd(pool_cents)}** budget applies to eligible cells (buy-plan may leave part **unallocated**). "
        "Categories are inferred from Growflow **ProductCategory.Name** plus **Product.Name** "
        "so **Cartridges** and **Disposables** stay separate (AIO/disposable keywords vs 510/vape-cart; "
        "combined or wrong categories are split from the product title). "
        "Pool substrings also include *vape* / *vapor* so generic vape aisles are not dropped. "
        "Other buckets: *edible*, *preroll*, *topical*; *infused* + *preroll* → **Infused prerolls**. "
        "The main section is **Brand → categories → breakdown**: each brand lists its product categories "
        "and gross / projected pool $ per category (rows sum to that brand's total pool share)."
    )
    L("")

    L(f"## Top {args.top_brands} brands (all focus categories combined)")
    L("")
    L("Ranked by **gross sales** in the focus categories only.")
    L("")
    L("| Rank | Brand | Gross sales | Share of format sales | Projected pool |")
    L("| ---: | --- | ---: | ---: | ---: |")
    for i, br in enumerate(top_n, start=1):
        g = brand_gross_fmt[br]
        pct = 100.0 * g / total_fmt
        L(f"| {i} | {br} | {_usd(g)} | {pct:.2f}% | {_usd(brand_pool_fmt[br])} |")
    L("")

    L("## Brand → categories → breakdown")
    L("")
    L(
        "Structure: **Brand** (heading) → **Category breakdown** (table: gross, pool $, % of that brand). "
        "Brands sorted by total projected pool (highest first)."
    )
    L("")
    if cap > 0:
        L(f"*Showing top **{cap}** brands by projected pool $; use `--max-brands-subprojection 0` for all.*")
        L("")

    for br in brand_order_sub:
        rows = sorted(
            by_brand_cats[br],
            key=lambda t: (
                BUCKET_DISPLAY_ORDER.index(t[0]) if t[0] in BUCKET_DISPLAY_ORDER else 99,
                t[0],
            ),
        )
        tot_g = brand_gross_fmt[br]
        tot_p = brand_pool_fmt[br]
        L(f"### {br}")
        L("")
        L(
            f"**Brand totals:** focus-category gross **{_usd(tot_g)}** | "
            f"projected pool **{_usd(tot_p)}**"
        )
        L("")
        L("#### Categories")
        L("")
        L("| Category | Gross | Projected pool $ | % of brand gross | % of brand pool |")
        L("| --- | ---: | ---: | ---: | ---: |")
        for buck, g, p in rows:
            pct_g = 100.0 * g / tot_g if tot_g > 0 else 0.0
            pct_p = 100.0 * p / tot_p if tot_p > 0 else 0.0
            L(f"| {buck} | {_usd(g)} | {_usd(p)} | {pct_g:.2f}% | {pct_p:.2f}% |")
        L("")

    L("## Category totals (all brands combined)")
    L("")
    L("Roll-up of **gross** and **pool $** by product category across every brand.")
    L("")
    L("| Category | Category gross | Share of format sales | Category pool $ |")
    L("| --- | ---: | ---: | ---: |")
    for buck in BUCKET_DISPLAY_ORDER:
        if buck not in bucket_gross:
            continue
        g = bucket_gross[buck]
        p = bucket_pool[buck]
        L(f"| {buck} | {_usd(g)} | {100.0 * g / total_fmt:.2f}% | {_usd(p)} |")
    L("")

    L("## Appendix: by category first (then brands)")
    L("")
    L("Same numbers as above, organized **category → brand** if you prefer that view.")
    L("")
    for buck in BUCKET_DISPLAY_ORDER:
        if buck not in bucket_gross:
            continue
        pairs = [(br, pair_gross[(buck, br)], pair_pool[(buck, br)]) for br in brand_gross_fmt if (buck, br) in pair_gross]
        pairs = [(br, g, p) for br, g, p in pairs if g > 0]
        pairs.sort(key=lambda x: -x[1])
        if not pairs:
            continue
        L(f"### {buck}")
        L("")
        L(f"**Category total gross:** {_usd(bucket_gross[buck])}  |  **Category pool:** {_usd(bucket_pool[buck])}")
        L("")
        show = pairs[: args.max_rows_per_category]
        rest = pairs[args.max_rows_per_category :]
        L("| Brand | Gross in category | Projected pool $ |")
        L("| --- | ---: | ---: |")
        for br, g, p in show:
            L(f"| {br} | {_usd(g)} | {_usd(p)} |")
        if rest:
            rg = sum(x[1] for x in rest)
            rp = sum(x[2] for x in rest)
            L(f"| *All other brands ({len(rest)} rows)* | {_usd(rg)} | {_usd(rp)} |")
        L("")

    if args.biweek_top > 0 and args.biweek_days >= 1:
        n_periods = num_biweek_periods(span_inclusive_days, args.biweek_days)
        L("## Best performers by 2-week interval (focus categories)")
        L("")
        L(
            f"Within each **{args.biweek_days}-day** store-local slice, brands ranked by **gross** "
            f"in edibles / cartridges / disposables / prerolls / infused prerolls / topicals only "
            f"(same exclusions as the pool). Top **{args.biweek_top}** per slice."
        )
        L("")
        for idx in range(n_periods):
            a, b = biweek_local_range(
                report_start_local,
                idx,
                args.biweek_days,
                report_end_local,
            )
            brands = biweek_by_brand.get(idx, {})
            ranked = sorted(brands.items(), key=lambda x: -x[1])[: args.biweek_top]
            period_gross = sum(brands.values())
            L(f"### Interval {idx + 1}: **{a.isoformat()}** to **{b.isoformat()}**")
            L("")
            L(f"**Slice gross (pool-eligible focus categories):** {_usd(period_gross)}")
            L("")
            if not ranked:
                L("*No qualifying sales in this slice.*")
                L("")
                continue
            L("| Rank | Brand | Gross | Share of slice |")
            L("| ---: | --- | ---: | ---: |")
            for rnk, (br, gc) in enumerate(ranked, start=1):
                pct = 100.0 * gc / period_gross if period_gross > 0 else 0.0
                L(f"| {rnk} | {br} | {_usd(gc)} | {pct:.2f}% |")
            L("")

    if not args.no_layer2:
        if layer2_rows:
            append_layer2_markdown(
                L,
                rows=layer2_rows,
                pool_cents=pool_cents,
                span_inclusive_days=span_inclusive_days,
                buy_plan=args.allocation_mode == "buy-plan",
                velocity_days=velocity_span if args.allocation_mode == "buy-plan" else None,
                cash_cycle_days=float(args.cash_cycle_days),
                remaining_pool_unallocated_usd=remaining_pool_unallocated_usd
                if args.allocation_mode == "buy-plan"
                else 0.0,
            )
            csv_path = args.layer2_csv or args.out.with_name(f"{args.out.stem}_layer2_recovery.csv")
            write_layer2_csv(
                csv_path,
                layer2_rows,
                allocation_mode=args.allocation_mode,
                velocity_window_days_run=str(
                    velocity_span if args.allocation_mode == "buy-plan" else span_inclusive_days
                ),
                cash_cycle_days_run=str(float(args.cash_cycle_days)),
                remaining_pool_unallocated_usd=f"{remaining_pool_unallocated_usd:.2f}"
                if args.allocation_mode == "buy-plan"
                else "",
                grouping_level=PLANNER_GROUPING_LEVEL,
                schema_validated=PLANNER_SCHEMA_VALIDATED,
                schema_source=PLANNER_SCHEMA_SOURCE,
                unit_model_note=PLANNER_UNIT_MODEL_NOTE,
            )
            print(f"Wrote {csv_path.resolve()}", flush=True)
        else:
            L("## Layer 2: velocity & COG recovery (required)")
            L("")
            L("*No brand × category rows with positive allocation; layer 2 skipped.*")
            L("")

    L("---")
    L("*Tool: `scripts/build_projection_by_category_brand.py`*")
    L("")

    if args.compare_modes:
        cmp_results: list[tuple[str, list[tuple[str, str, int, dict]], dict[str, Any]]] = []
        for mode in ("buy-plan", "throughput", "gross-share"):
            pp, ps = allocate_for_mode(
                mode,
                pool_cents,
                keys,
                pair_gross,
                pair_units,
                pair_cog,
                span_inclusive_days,
                total_fmt,
                pair_units_recent,
                pair_gross_recent,
                pair_cog_recent,
                velocity_span,
                pair_units_with_cog=pair_units_with_cog,
                pair_units_with_cog_recent=pair_units_with_cog_recent,
                pair_units_per_day_recent=pair_units_per_day_recent,
                min_units_per_week=float(args.min_units_per_week),
                buy_plan_max_rows=max(1, int(args.buy_plan_max_rows)),
                min_allocated_cents=min_cents,
                pool_top_n=int(args.pool_top_n),
                cash_cycle_days=float(args.cash_cycle_days),
            )
            rows_m = build_layer2_rows_list(
                mode,
                keys,
                pp,
                ps,
                pair_units_recent,
                pair_gross_recent,
                pair_cog_recent,
                velocity_span,
                pair_units_per_day_recent,
                pair_units,
                pair_gross,
                pair_cog,
                span_inclusive_days,
                pair_units_with_cog=pair_units_with_cog,
                pair_units_with_cog_recent=pair_units_with_cog_recent,
                cash_cycle_days=float(args.cash_cycle_days),
            )
            cmp_results.append((mode, rows_m, compare_allocation_modes_metrics(mode, rows_m)))
        cmp_path = args.compare_modes_out or args.out.with_name(f"{args.out.stem}_allocation_compare.md")
        cmp_path.parent.mkdir(parents=True, exist_ok=True)
        cmp_path.write_text(
            render_allocation_compare_md(
                pool_cents=pool_cents,
                velocity_span=velocity_span,
                span_inclusive_days=span_inclusive_days,
                min_cents=min_cents,
                buy_plan_max_rows=max(1, int(args.buy_plan_max_rows)),
                min_upw=float(args.min_units_per_week),
                pool_top_n=int(args.pool_top_n),
                cash_cycle_days=float(args.cash_cycle_days),
                results=cmp_results,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {cmp_path.resolve()} (compare-modes)", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines_out), encoding="utf-8")
    print(f"Wrote {args.out.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
