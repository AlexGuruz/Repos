"""Cartel multipack / 7pk identification from Growflow product and brand fields.

**Transfers (canonical signifier)** — Cartel preroll multipacks are tracked when the line matches:

- **Brand:** ``Cartel Oil Co`` (or legacy exact ``Cartel``)
- **Product name:** ``Infused`` + ``Pre-Roll`` / ``Preroll`` + ``Bundle`` + **8.4g** weight

(Display strings often look like: ``Cartel Oil Co | Infused Pre-Roll Bundle + 8.4G`` — the ``|`` is UI,
not required in the API payload.)

**Order lines** — Same signifier path, plus explicit ``7pk`` in the name and legacy ``cartel`` + ``8.4g``
rules where the fetch regex already scoped Cartel preroll product names.

**Human-readable spec (for future transfer/order runs):** ``docs/GROWFLOW_CARTEL_TRANSFER_IDENTIFIERS.md``.
"""
from __future__ import annotations

import re
from typing import Any, Pattern

FOURTEEN_PK = re.compile(r"(?i)\b14[\s-]*pk\b|14PK")
FIVE_PK = re.compile(r"(?i)\b5[\s-]*pk\b|5PK")
SEVEN_PK = re.compile(r"(?i)\b7[\s-]*pk\b|7PK")
WEIGHT_8_4G = re.compile(r"(?i)8\.4\s*g\b|8\.4G\b")
EXC_7PK = re.compile(r"(?i)disposable|cartridge")
# Product name contains: infused + bundle + pre-roll or preroll + 8.4g/8.4G (order-independent).
_RX_INFUSED_BUNDLE_8_4 = re.compile(
    r"(?i)(?=.*\binfused\b)(?=.*(\bpre[\s-]?roll\b|\bpreroll\b))(?=.*\bbundle\b)"
    r"(?=.*(?:8\.4\s*g|8\.4G))"
)
_RX_CARTEL_OIL_CO = re.compile(r"(?i)\bcartel\s+oil\s+co\b")


def product_brand_name(product: dict[str, Any] | None) -> str:
    if not product or not isinstance(product, dict):
        return ""
    bd = product.get("Brand") if isinstance(product.get("Brand"), dict) else {}
    return str((bd or {}).get("Name") or "").strip()


def order_item_brand_name(n: dict[str, Any]) -> str:
    return product_brand_name(n.get("Product") if isinstance(n.get("Product"), dict) else None)


def is_cartel_retail_brand(brand_name: str) -> bool:
    """Growflow Brand.Name for Cartel multipack vendor lines."""
    n = (brand_name or "").strip().lower()
    if not n:
        return False
    if n == "cartel":
        return True
    return bool(_RX_CARTEL_OIL_CO.search(brand_name or ""))


def matches_cartel_transfer_preroll_pack_signifiers(product_name: str, brand_name: str = "") -> bool:
    """
    True when product + brand match the transfer tracking pattern:
    Cartel Oil Co (on brand or in name) + Infused Pre-Roll Bundle + 8.4g in product name.
    """
    n = product_name or ""
    if not _RX_INFUSED_BUNDLE_8_4.search(n):
        return False
    blob = f"{brand_name} {n}"
    if not _RX_CARTEL_OIL_CO.search(blob):
        return False
    if EXC_7PK.search(n):
        return False
    if FOURTEEN_PK.search(n):
        return False
    return True


def cartel_pack_line_kept_after_fetch(name: str, brand_name: str, *, pack_re: Pattern[str]) -> bool:
    """
    Client-side filter for OrderItems already pulled with a broad Cartel / bundle server regex.
    Drops disposables; keeps signifier bundles or legacy PACK_RE matches on name or brand+name blob.
    """
    nm = name or ""
    if EXC_7PK.search(nm):
        return False
    if matches_cartel_transfer_preroll_pack_signifiers(nm, brand_name):
        return True
    blob = f"{brand_name} {nm}".strip()
    return bool(pack_re.search(nm) or (is_cartel_retail_brand(brand_name) and pack_re.search(blob)))


_RX_BLUNT = re.compile(r"(?i)\bblunt\b")
_RX_12G = re.compile(r"(?i)\b1\.2\s*g\b|\b1\.2G\b")
_RX_ANY_PK = re.compile(r"(?i)\b(?:5|7|14)[\s-]*pk\b|(?:5|7|14)PK\b")

CARTEL_PACE_7PK = "7pk 8.4g preroll"
CARTEL_PACE_5PK = "5pk preroll"
CARTEL_PACE_14PK = "14pk preroll"
CARTEL_PACE_SINGLE_12G = "Single 1.2g preroll"
CARTEL_PACE_BLUNTS = "Blunts"
CARTEL_PACE_OTHER = "Other Cartel"
CARTEL_PACE_UNIDENTIFIED = "Unidentified"

CARTEL_PACE_BUCKETS_ORDER: tuple[str, ...] = (
    CARTEL_PACE_7PK,
    CARTEL_PACE_5PK,
    CARTEL_PACE_14PK,
    CARTEL_PACE_SINGLE_12G,
    CARTEL_PACE_BLUNTS,
    CARTEL_PACE_OTHER,
    CARTEL_PACE_UNIDENTIFIED,
)


def is_cartel_product_line(name: str, brand_name: str = "") -> bool:
    """True when brand or product title indicates Cartel vendor."""
    n = name or ""
    if is_cartel_retail_brand(brand_name):
        return True
    return bool(re.search(r"(?i)\bcartel\b", n))


def cartel_reorder_pace_bucket(name: str, brand_name: str = "") -> str:
    """
    Cartel SKU class for receipt-anchored reorder pacing.

    Each transfer line maps to exactly one bucket so the full order can be tracked per format.
    """
    n = (name or "").strip()
    if not n:
        return CARTEL_PACE_UNIDENTIFIED
    if not is_cartel_product_line(n, brand_name):
        return CARTEL_PACE_OTHER

    if _RX_BLUNT.search(n):
        return CARTEL_PACE_BLUNTS

    if FOURTEEN_PK.search(n):
        return CARTEL_PACE_14PK

    if is_cartel_7pk_product_name(n, brand_name=brand_name) or bool(SEVEN_PK.search(n)):
        return CARTEL_PACE_7PK

    if FIVE_PK.search(n):
        return CARTEL_PACE_5PK

    if _RX_12G.search(n) and not _RX_ANY_PK.search(n):
        return CARTEL_PACE_SINGLE_12G

    return CARTEL_PACE_OTHER


def is_cartel_7pk_product_name(
    name: str,
    *,
    brand_name: str = "",
    pack_re: Pattern[str] | None = None,
) -> bool:
    """
    True if this row counts as a Cartel 7pk / infused bundle multipack unit.

    ``pack_re`` — when set, the row must either match transfer signifiers or satisfy ``pack_re`` on
    product name or ``brand_name + name`` (same as fetch client filter).
    When ``pack_re`` is None (e.g. package audit), signifiers or legacy name-based rules apply using
    ``brand_name`` when the product name omits ``cartel``.
    """
    n = name or ""
    bn = brand_name or ""

    if matches_cartel_transfer_preroll_pack_signifiers(n, bn):
        return True

    if pack_re is not None:
        if not cartel_pack_line_kept_after_fetch(n, bn, pack_re=pack_re):
            return False
    elif not ("cartel" in n.lower() or is_cartel_retail_brand(bn)):
        return False

    if EXC_7PK.search(n):
        return False
    if FOURTEEN_PK.search(n):
        return False
    return bool(SEVEN_PK.search(n) or WEIGHT_8_4G.search(n))
