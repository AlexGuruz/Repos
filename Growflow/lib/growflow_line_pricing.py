"""
Growflow Retail order-line pricing (tax-inclusive menu / out-the-door).

Nugz uses **tax-inclusive menu prices** (flat OTD on the shelf). On the API those are **not**
``GrossPrice`` alone.

Validated on nugzdispensary (2026-06):

| Meaning | API field | Notes |
|--------|-----------|--------|
| Menu / list OTD per item | ``findProducts.SalesPrice`` | Catalog cents (e.g. 7pk = 3700 → $37) |
| Menu OTD at time of sale | ``OrderItems.OriginalPrice`` | Matches ``Product.SalesPrice`` on undiscounted lines |
| Pre-tax portion rung on line | ``OrderItems.GrossPrice`` | Lower than menu; taxes are separate line elements |
| Tax on line | ``OrderItems.Taxes[].value.taxAmount`` | JSON in ``Element.value`` |
| Customer OTD collected | ``GrossPrice`` + sum(taxAmount) | Matches register; ≈ ``OriginalPrice`` when no discount |
| Discounted pre-tax charge | ``OrderItems.Price`` | Can be below ``OriginalPrice`` (promo) |

``NetPrice`` is **not** OTD; it tracks another net slice (often close to ``GrossPrice``).

Use ``menu_price_cents`` for flat menu dollars; ``collected_otd_cents`` for actual tendered amount.
"""
from __future__ import annotations

import json
from typing import Any


def parse_tax_element_value(raw: object) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def line_tax_cents(node: dict[str, Any]) -> int:
    """Sum non-exempt ``taxAmount`` from ``OrderItems.Taxes``."""
    total = 0
    for el in node.get("Taxes") or []:
        if not isinstance(el, dict):
            continue
        val = parse_tax_element_value(el.get("value"))
        if not val or val.get("exempt"):
            continue
        try:
            total += int(val.get("taxAmount") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _int_cents(v: object) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def menu_price_cents(node: dict[str, Any]) -> int:
    """
    Tax-inclusive list / menu price for the line.

    Prefer ``OriginalPrice``, then nested ``Product.SalesPrice``.
    """
    orig = _int_cents(node.get("OriginalPrice"))
    if orig > 0:
        return orig
    prod = node.get("Product")
    if isinstance(prod, dict):
        sp = _int_cents(prod.get("SalesPrice"))
        if sp > 0:
            return sp
    return 0


def collected_otd_cents(node: dict[str, Any]) -> int:
    """Actual out-the-door collected on the line (pre-tax gross + line taxes)."""
    return _int_cents(node.get("GrossPrice")) + line_tax_cents(node)


def pre_tax_gross_cents(node: dict[str, Any]) -> int:
    """Pre-tax portion on the line (``GrossPrice``). Not menu OTD."""
    return _int_cents(node.get("GrossPrice"))
