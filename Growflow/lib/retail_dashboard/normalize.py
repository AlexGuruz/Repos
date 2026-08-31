"""Normalize GrowFlow API nodes into fact-store rows."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from lib.brand_category_normalize import apply_brand_category_canonicals
from lib.growflow_line_pricing import collected_otd_cents, line_tax_cents, menu_price_cents


def _int_cents(v: object) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def first_order_fragment(node: dict[str, Any]) -> dict[str, Any]:
    """Extract first Orders union fragment from an order line."""
    orders = node.get("Orders")
    if isinstance(orders, list):
        for o in orders:
            if isinstance(o, dict) and o.get("objectId"):
                return o
    if isinstance(orders, dict) and orders.get("objectId"):
        return orders
    return {}


def extract_user(order: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    user = order.get("User")
    if not isinstance(user, dict):
        return None, None, None
    uid = str(user.get("objectId") or "").strip() or None
    name = str(user.get("FullName") or user.get("username") or "").strip() or None
    username = str(user.get("username") or "").strip() or None
    return uid, name, username


def extract_store(node: dict[str, Any], order: dict[str, Any]) -> tuple[str | None, str | None]:
    for src in (node.get("Store"), order.get("Store")):
        if isinstance(src, dict) and src.get("objectId"):
            return str(src["objectId"]), str(src.get("Name") or "")
    return None, None


def infer_channel(order: dict[str, Any]) -> str:
    """in_store | online | unknown — PreOrderType non-null may indicate online/preorder."""
    pot = order.get("PreOrderType")
    if pot is not None and str(pot).strip():
        return "online"
    return "in_store"


def is_return_order(order: dict[str, Any], line_gross: int, line_net: int) -> bool:
    otype = str(order.get("Type") or "").lower()
    if "return" in otype or "refund" in otype:
        return True
    if _int_cents(order.get("Total")) < 0:
        return True
    if line_gross < 0 or line_net < 0:
        return True
    return False


def sold_date_local(sold_at: str, tz: ZoneInfo) -> str:
    dt = datetime.fromisoformat(sold_at.replace("Z", "+00:00"))
    return dt.astimezone(tz).date().isoformat()


def normalize_order_line(
    node: dict[str, Any],
    *,
    tz: ZoneInfo,
    ingest_run_id: str,
    landed_cost_by_product: dict[str, int] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """
    Returns (order_row, line_row). Either may be None if objectId missing.
    """
    line_id = str(node.get("objectId") or "").strip()
    sold_at = str(node.get("SoldAt") or "").strip()
    if not line_id or not sold_at:
        return None, None

    order = first_order_fragment(node)
    order_id = str(order.get("objectId") or "").strip() or None
    store_id, _store_name = extract_store(node, order)
    user_id, user_name, username = extract_user(order)

    menu = menu_price_cents(node)
    collected = collected_otd_cents(node)
    tax = line_tax_cents(node)
    gross = _int_cents(node.get("GrossPrice"))
    net = _int_cents(node.get("NetPrice"))
    discount = max(0, menu - collected) if menu > 0 else max(0, gross - _int_cents(node.get("Price")))

    prod = node.get("Product") if isinstance(node.get("Product"), dict) else {}
    cat = node.get("ProductCategory") or prod.get("ProductCategory") or {}
    brand_raw = ""
    if isinstance(prod.get("Brand"), dict):
        brand_raw = str(prod["Brand"].get("Name") or "").strip()
    category_raw = str(cat.get("Name") or "").strip()
    product_id = str(prod.get("objectId") or "").strip() or None

    pkg = node.get("Package") if isinstance(node.get("Package"), dict) else {}
    package_id = str(pkg.get("objectId") or "").strip() or None

    ret = is_return_order(order, gross, net)
    channel = infer_channel(order)

    discounts_cents = _int_cents(order.get("Discounts"))
    subtotal_cents = _int_cents(order.get("Subtotal"))
    has_discount = 1 if discounts_cents > 0 or discount > 0 else 0

    order_row = None
    if order_id:
        order_row = {
            "object_id": order_id,
            "completed_at": order.get("CompletedAt"),
            "total_cents": _int_cents(order.get("Total")),
            "subtotal_cents": subtotal_cents,
            "discounts_cents": discounts_cents,
            "order_type": order.get("Type"),
            "status": order.get("Status"),
            "pre_order_type": order.get("PreOrderType"),
            "budtender_user_id": user_id,
            "store_object_id": store_id,
            "has_discount": has_discount,
            "is_return": 1 if ret else 0,
        }

    landed = None
    if product_id and landed_cost_by_product:
        landed = landed_cost_by_product.get(product_id)

    canon = apply_brand_category_canonicals({"brand_name": brand_raw, "category_name": category_raw})

    line_row = {
        "object_id": line_id,
        "sold_at": sold_at,
        "sold_date_local": sold_date_local(sold_at, tz),
        "order_object_id": order_id,
        "store_object_id": store_id,
        "budtender_user_id": user_id,
        "budtender_name": user_name or username,
        "gross_price_cents": gross,
        "net_price_cents": net,
        "cog_cents": _int_cents(node.get("COG")) or None,
        "original_price_cents": _int_cents(node.get("OriginalPrice")) or None,
        "price_cents": _int_cents(node.get("Price")) or None,
        "tax_cents": tax,
        "collected_otd_cents": collected,
        "discount_cents": discount,
        "is_return": 1 if ret else 0,
        "channel": channel,
        "product_object_id": product_id,
        "brand_raw": brand_raw,
        "brand_canonical": str(canon.get("canonical_brand") or brand_raw),
        "category_raw": category_raw,
        "category_canonical": str(canon.get("canonical_category") or category_raw),
        "package_object_id": package_id,
        "landed_cost_cents": landed,
        "ingest_run_id": ingest_run_id,
    }
    return order_row, line_row


def normalize_product(node: dict[str, Any]) -> dict[str, Any]:
    brand = node.get("Brand") if isinstance(node.get("Brand"), dict) else {}
    cat = node.get("ProductCategory") if isinstance(node.get("ProductCategory"), dict) else {}
    return {
        "object_id": str(node.get("objectId") or ""),
        "name": node.get("Name"),
        "sku": node.get("SKU"),
        "brand_id": brand.get("objectId"),
        "category_id": cat.get("objectId"),
        "sales_price_cents": _int_cents(node.get("SalesPrice")) or None,
    }
