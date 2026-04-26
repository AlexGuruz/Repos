"""
Merit weights for brand-level COG pool: margin (where COG exists), 14-day velocity,
and turnover vs on-hand inventory cost.

Pure logic — testable without API calls.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Sequence


def parse_iso_utc(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        return None


# ProductCategory.Name substrings (case-insensitive OR). Covers edibles, cartridges,
# disposables, prerolls, infused prerolls ("infused ... preroll" still matches "preroll"),
# topicals, and generic vape / vapor categories (split into Cartridges vs Disposables via
# product_format_bucket — not by this substring alone).
FORMAT_PRODUCT_POOL_SUBSTRINGS: tuple[str, ...] = (
    "edible",
    "cartridge",
    "disposable",
    "topical",
    "preroll",
    "pre-roll",
    "vape",
    "vapor",
)

# Resolved buckets that count as the “format product pool” for merit allocation / packages
# when category name alone does not match FORMAT_PRODUCT_POOL_SUBSTRINGS.
FORMAT_POOL_BUCKETS: frozenset[str] = frozenset(
    {
        "Edibles",
        "Cartridges",
        "Disposables",
        "Prerolls",
        "Infused prerolls",
        "Topicals",
    }
)


def order_line_product_category_name(n: dict[str, Any]) -> str:
    pc = n.get("ProductCategory") or {}
    return str(pc.get("Name") or "").strip()


def order_line_product_name(n: dict[str, Any]) -> str:
    prod = n.get("Product") or {}
    return str(prod.get("Name") or "").strip()


def order_line_format_bucket(n: dict[str, Any]) -> str:
    """
    Single entry point for projection / reporting: order item node -> format bucket.
    Uses ProductCategory.Name + Product.Name (disposable vs cartridge disambiguation).

    TODO(schema truth): Replace inference with findProductCategories / product taxonomy when validated
    (docs/GROWFLOW_PLANNER_DATA_MAPPING.md).
    """
    return product_format_bucket(order_line_product_category_name(n), order_line_product_name(n))


def package_product_name(pkg: dict[str, Any]) -> str:
    prod = pkg.get("Product") or {}
    return str(prod.get("Name") or "").strip()


def package_product_category_name(pkg: dict[str, Any]) -> str:
    prod = pkg.get("Product") or {}
    pc = prod.get("ProductCategory") or {}
    return str(pc.get("Name") or "").strip()


def category_matches_format_substrings(name: str | None, substrings: Sequence[str]) -> bool:
    if not name or not str(name).strip():
        return False
    lower = str(name).strip().lower()
    return any(s.lower() in lower for s in substrings)


def order_line_in_format_product_pool(
    n: dict[str, Any],
    substrings: Sequence[str] | None = None,
) -> bool:
    subs = substrings if substrings is not None else FORMAT_PRODUCT_POOL_SUBSTRINGS
    if category_matches_format_substrings(order_line_product_category_name(n), subs):
        return True
    return order_line_format_bucket(n) in FORMAT_POOL_BUCKETS


def package_in_format_product_pool(
    pkg: dict[str, Any],
    substrings: Sequence[str] | None = None,
) -> bool:
    subs = substrings if substrings is not None else FORMAT_PRODUCT_POOL_SUBSTRINGS
    if category_matches_format_substrings(package_product_category_name(pkg), subs):
        return True
    return package_format_bucket(pkg) in FORMAT_POOL_BUCKETS


def package_format_bucket(pkg: dict[str, Any]) -> str:
    """Package node -> same format buckets as order lines (category + Product.Name)."""
    return product_format_bucket(package_product_category_name(pkg), package_product_name(pkg))


_NON_DISPOSABLE_RE = re.compile(r"non[- ]disposable", re.IGNORECASE)
_DISPO_WORD_RE = re.compile(r"\bdispo\b", re.IGNORECASE)


def _text_implies_disposable(text: str) -> bool:
    """True if name suggests an all-in-one / disposable vape (not 'non-disposable')."""
    if not text or not str(text).strip():
        return False
    t = str(text).strip().lower()
    if _NON_DISPOSABLE_RE.search(t):
        return False
    if "disposable" in t:
        return True
    if _DISPO_WORD_RE.search(t):
        return True
    if re.search(r"\bdispos\b", t):
        return True
    if "all-in-one" in t or "all in one" in t:
        return True
    if re.search(r"\baio\b", t):
        return True
    if re.search(r"\b\d[\d.]*\s*g\s+aio\b", t):
        return True
    # Common disposable form factors when paired with vape context
    if "vape" in t and re.search(r"\b(stick|bar)\b", t):
        return True
    return False


def _text_implies_cartridge_product(product_lower: str) -> bool:
    """Product title hints at 510 / replaceable cartridge (not brand names like 'Cartel')."""
    if not product_lower:
        return False
    if "cartridge" in product_lower:
        return True
    if re.search(r"\bvape\s+carts?\b", product_lower):
        return True
    if re.search(r"\b510\b", product_lower):
        return True
    if re.search(r"\bcarts?\b", product_lower):
        return True
    return False


def _category_cartridge_signal(category_lower: str) -> bool:
    if not category_lower:
        return False
    if "cartridge" in category_lower:
        return True
    if re.search(r"\b510\b", category_lower):
        return True
    if re.search(r"\bcarts?\b", category_lower):
        return True
    return False


def _category_disposable_signal(category_lower: str) -> bool:
    if not category_lower:
        return False
    if _text_implies_disposable(category_lower):
        return True
    if re.search(r"\baio\b", category_lower):
        return True
    if "all-in-one" in category_lower or "all in one" in category_lower:
        return True
    return False


def _classify_vape_product_only(product_lower: str) -> str | None:
    """
    When Growflow ProductCategory misses vape taxonomy, use Product.Name only.
    Tie-break if both signals: explicit 510 / vape cart -> Cartridges; else Disposables.
    """
    if not product_lower:
        return None
    prod_disp = _text_implies_disposable(product_lower)
    prod_cart = _text_implies_cartridge_product(product_lower)
    if prod_disp and prod_cart:
        if re.search(r"\b(510|thread)\b", product_lower) and "disposable" not in product_lower:
            return "Cartridges"
        if re.search(r"\bvape\s+carts?\b", product_lower):
            return "Cartridges"
        return "Disposables"
    if prod_disp:
        return "Disposables"
    if prod_cart:
        return "Cartridges"
    return None


def _classify_vape_bucket(category_lower: str, product_lower: str) -> str | None:
    """
    Map vape-related Growflow categories (+ optional Product.Name) to Cartridges vs Disposables.

    Growflow sometimes uses combined categories (e.g. cartridges and disposables in one name) or
    puts disposable hardware under a category whose name contains 'cartridge' first; we use
    Product.Name when the category is ambiguous.
    """
    cat_cart = _category_cartridge_signal(category_lower)
    cat_disp = _category_disposable_signal(category_lower)
    prod_disp = _text_implies_disposable(product_lower)
    prod_cart = _text_implies_cartridge_product(product_lower)
    vague_vape = not cat_cart and not cat_disp and (
        re.search(r"\bvape\b", category_lower) or "vapor" in category_lower
    )

    if cat_disp and not cat_cart:
        return "Disposables"
    if cat_cart and not cat_disp:
        if prod_disp and not _NON_DISPOSABLE_RE.search(product_lower):
            return "Disposables"
        return "Cartridges"
    if cat_cart and cat_disp:
        if prod_disp:
            return "Disposables"
        if prod_cart and not prod_disp:
            return "Cartridges"
        return "Cartridges"
    if vague_vape:
        if prod_disp:
            return "Disposables"
        if prod_cart:
            return "Cartridges"
        # Category is vape-shaped but title has no signal: plan as cartridges (510 SKUs)
        # so we do not drop the row into Other / exclude from pool.
        return "Cartridges"
    return None


def product_format_bucket(category_name: str | None, product_name: str | None = None) -> str:
    """
    Map Growflow ProductCategory.Name (+ optional Product.Name) to a single reporting bucket.
    Infused prerolls are detected before generic prerolls / edibles.
    Disposable vs cartridge uses category first; combined or misleading categories use product name.
    """
    if not category_name or not str(category_name).strip():
        s = ""
    else:
        s = str(category_name).strip().lower()
    p = str(product_name).strip().lower() if product_name and str(product_name).strip() else ""

    if s and "infused" in s and ("preroll" in s or "pre-roll" in s):
        return "Infused prerolls"
    if s and "topical" in s:
        return "Topicals"
    if s and "edible" in s:
        return "Edibles"

    vape = _classify_vape_bucket(s, p) if s else None
    if vape is not None:
        return vape
    # Category empty but product might still describe a vape SKU (rare on order lines)
    if not s and p:
        pv = _classify_vape_product_only(p)
        if pv is not None:
            return pv

    if s and ("preroll" in s or "pre-roll" in s):
        return "Prerolls"
    # Product title proves vape format even when Growflow category is unrelated (e.g. Concentrates)
    pv2 = _classify_vape_product_only(p)
    if pv2 is not None:
        return pv2
    return "Other"


def brand_label_from_line(n: dict[str, Any]) -> str:
    prod = n.get("Product") or {}
    bo = prod.get("Brand")
    if isinstance(bo, dict):
        name = bo.get("Name")
    else:
        name = None
    return str(name).strip() if name and str(name).strip() else "(no brand)"


def build_sku_to_brand(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Most common brand label per product SKU from order lines."""
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for n in nodes:
        prod = n.get("Product") or {}
        sku = (prod.get("SKU") or n.get("SKU") or "").strip()
        if not sku:
            continue
        counts[sku][brand_label_from_line(n)] += 1
    return {sku: ctr.most_common(1)[0][0] for sku, ctr in counts.items() if ctr}


def package_brand(pkg: dict[str, Any], sku_to_brand: dict[str, str]) -> str:
    prod = pkg.get("Product") or {}
    bo = prod.get("Brand")
    if isinstance(bo, dict) and (bo.get("Name") or "").strip():
        return str(bo["Name"]).strip()
    sku = (prod.get("SKU") or pkg.get("SKU") or "").strip()
    if sku and sku in sku_to_brand:
        return sku_to_brand[sku]
    return "(no brand)"


def cents_field(x: Any) -> int:
    try:
        return int(x) if x is not None else 0
    except (TypeError, ValueError):
        return 0


@dataclass
class BrandMeritRow:
    brand: str
    gross_year_cents: int
    gross_14d_cents: int
    gross_prev14_cents: int
    margin_cents: int
    gross_with_cog_cents: int
    lines_year: int
    lines_with_cog: int
    inventory_cost_cents: int
    package_units: int
    margin_ratio: float  # margin / gross_with_cog
    velocity_ratio: float  # gross_14d / max(gross_prev14, 1)
    turnover_proxy: float  # gross_14d / (inventory_cost + 100)


def _empty_order_acc() -> dict[str, int]:
    return {
        "gross_y": 0,
        "gross_14": 0,
        "gross_prev": 0,
        "margin": 0,
        "gross_cog": 0,
        "lines_y": 0,
        "lines_cog": 0,
    }


def merge_sku_brand_counters(
    lines: list[dict[str, Any]],
    counters: dict[str, Counter[str]],
) -> None:
    for n in lines:
        prod = n.get("Product") or {}
        sku = (prod.get("SKU") or n.get("SKU") or "").strip()
        if not sku:
            continue
        counters[sku][brand_label_from_line(n)] += 1


def accumulate_order_lines_chunk(
    lines: list[dict[str, Any]],
    acc: dict[str, dict[str, int]],
    *,
    today_local: date,
    velocity_days: int,
    store_tz: Any,
) -> None:
    """Merge one batch of order lines into running per-brand counters (in-place)."""
    start_recent = today_local - timedelta(days=velocity_days - 1)
    start_prev = today_local - timedelta(days=2 * velocity_days - 1)
    end_prev = today_local - timedelta(days=velocity_days)

    for n in lines:
        b = brand_label_from_line(n)
        gp = cents_field(n.get("GrossPrice"))
        cog = n.get("COG")
        sold = parse_iso_utc(n.get("SoldAt"))
        if sold is None:
            continue
        if b not in acc:
            acc[b] = _empty_order_acc()
        a = acc[b]
        ld = sold.astimezone(store_tz).date()
        a["lines_y"] += 1
        a["gross_y"] += gp
        if start_recent <= ld <= today_local:
            a["gross_14"] += gp
        if start_prev <= ld <= end_prev:
            a["gross_prev"] += gp
        try:
            cog_i = int(cog) if cog is not None else None
        except (TypeError, ValueError):
            cog_i = None
        if cog_i is not None and 0 <= cog_i <= gp:
            a["lines_cog"] += 1
            a["margin"] += gp - cog_i
            a["gross_cog"] += gp


def rows_from_order_acc_and_packages(
    acc: dict[str, dict[str, int]],
    packages: list[dict[str, Any]],
    sku_to_brand: dict[str, str],
) -> dict[str, BrandMeritRow]:
    """Build BrandMeritRow map from merged order accumulators + package list."""
    inv_cost: dict[str, int] = defaultdict(int)
    pkg_units: dict[str, int] = defaultdict(int)
    for pkg in packages:
        b = package_brand(pkg, sku_to_brand)
        cq = cents_field(pkg.get("CurrentQty"))
        if cq <= 0:
            continue
        cost = cents_field(pkg.get("Cost"))
        inv_cost[b] += cq * cost
        pkg_units[b] += cq

    brands = set(acc.keys()) | set(inv_cost.keys())
    out: dict[str, BrandMeritRow] = {}
    for b in sorted(brands):
        a = acc.get(b) or _empty_order_acc()
        g14 = a["gross_14"]
        gpr = a["gross_prev"]
        gc = a["gross_cog"]
        mr = (a["margin"] / gc) if gc > 0 else 0.0
        ic = inv_cost[b]
        tp = g14 / (ic + 100)
        out[b] = BrandMeritRow(
            brand=b,
            gross_year_cents=a["gross_y"],
            gross_14d_cents=g14,
            gross_prev14_cents=gpr,
            margin_cents=a["margin"],
            gross_with_cog_cents=gc,
            lines_year=a["lines_y"],
            lines_with_cog=a["lines_cog"],
            inventory_cost_cents=ic,
            package_units=pkg_units[b],
            margin_ratio=mr,
            velocity_ratio=g14 / max(gpr, 1),
            turnover_proxy=tp,
        )
    return out


def aggregate_brand_merit_inputs(
    order_lines: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    *,
    today_local: date,
    velocity_days: int = 14,
    sku_to_brand: dict[str, str] | None = None,
    store_tz: Any,
) -> dict[str, BrandMeritRow]:
    """
    today_local: end of reporting window in store calendar.
    velocity_days: length of trailing window (default 14) and previous window of same length.
    """
    sku_map = sku_to_brand if sku_to_brand is not None else build_sku_to_brand(order_lines)
    acc: dict[str, dict[str, int]] = {}
    accumulate_order_lines_chunk(
        order_lines,
        acc,
        today_local=today_local,
        velocity_days=velocity_days,
        store_tz=store_tz,
    )
    return rows_from_order_acc_and_packages(acc, packages, sku_map)


def minmax_norm(values: list[float]) -> list[float]:
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [1.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def merit_weights(
    rows: list[BrandMeritRow],
    *,
    w_margin: float = 0.35,
    w_velocity14: float = 0.40,
    w_turnover: float = 0.25,
    min_year_gross_cents: int = 1,
) -> tuple[list[float], list[str]]:
    """
    Returns (weights aligned with rows, issue_flags).
    Rows with essentially no activity get weight 0.
    """
    issues: list[str] = []
    active: list[BrandMeritRow] = []
    for r in rows:
        if r.gross_year_cents < min_year_gross_cents and r.gross_14d_cents <= 0 and r.inventory_cost_cents <= 0:
            continue
        active.append(r)
    if not active:
        issues.append("NO_ACTIVE_BRANDS")
        return [0.0 for _ in rows], issues

    cov = sum(1 for r in active if r.lines_with_cog > 0) / max(len(active), 1)
    if cov < 0.25:
        issues.append(
            f"LOW_COG_COVERAGE: only {cov:.0%} of active brands have any lines with usable COG; margin scores are weak"
        )

    m_ratios = [r.margin_ratio for r in active]
    v_logs = [math.log1p(r.gross_14d_cents / 100.0) for r in active]
    t_logs = [math.log1p(r.turnover_proxy) for r in active]

    n_m = minmax_norm(m_ratios)
    n_v = minmax_norm(v_logs)
    n_t = minmax_norm(t_logs)

    wsum = w_margin + w_velocity14 + w_turnover
    if wsum <= 0:
        w_margin = w_velocity14 = w_turnover = 1 / 3
        wsum = 1.0

    raw = [
        (w_margin * n_m[i] + w_velocity14 * n_v[i] + w_turnover * n_t[i]) / wsum for i in range(len(active))
    ]
    # Map back to full rows list order: inactive brands weight 0
    by_brand = {active[i].brand: raw[i] for i in range(len(active))}
    weights = [by_brand.get(r.brand, 0.0) for r in rows]
    if sum(weights) <= 0:
        issues.append("ALL_WEIGHTS_ZERO_FALLBACK_TO_GROSS")
        total_g = sum(max(1, r.gross_year_cents) for r in rows)
        weights = [max(1, r.gross_year_cents) / total_g for r in rows]
    return weights, issues
