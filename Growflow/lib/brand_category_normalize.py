"""
Canonical brand/category mapping for normalized Growflow rows.

Reads ``config/brand_category_normalization.json`` (optional).
Adds ``canonical_brand``, ``canonical_category``, and mapping confidence tiers.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "brand_category_normalization.json"


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        return {"canonical_brands": {}, "canonical_categories": {}, "rules": []}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {"canonical_brands": {}, "canonical_categories": {}, "rules": []}


def _casefold_key(s: str) -> str:
    return str(s or "").strip().casefold()


def _lookup_table(table: Any, value: str) -> tuple[str, str]:
    """Return (canonical_label, confirmed|inferred)."""
    if not isinstance(table, dict):
        return value, "inferred"
    for k, v in table.items():
        if _casefold_key(str(k)) == _casefold_key(value):
            return str(v).strip(), "confirmed"
    return value.strip(), "inferred"


def _apply_category_rules(cfg: dict[str, Any], value: str) -> tuple[str, bool]:
    """Returns (possibly rewritten category, rule_matched)."""
    text = str(value).strip()
    rules = cfg.get("rules") or []
    if not isinstance(rules, list):
        return text, False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("field") or "") != "category_name":
            continue
        if str(rule.get("match") or "") != "substring":
            continue
        pat = str(rule.get("pattern") or "")
        if not pat:
            continue
        try:
            if re.search(pat, text, flags=re.IGNORECASE):
                return str(rule.get("canonical") or text).strip(), True
        except re.error:
            continue
    return text, False


def apply_brand_category_canonicals(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    cfg = load_config()
    brands_tbl = cfg.get("canonical_brands") or {}
    cats_tbl = cfg.get("canonical_categories") or {}

    if "brand_name" in out:
        raw = out.get("brand_name")
        if raw is not None and str(raw).strip() != "":
            canon, tier = _lookup_table(brands_tbl, str(raw))
            out["canonical_brand"] = canon
            out["brand_mapping_confidence"] = tier
        else:
            out.setdefault("canonical_brand", None)
            out.setdefault("brand_mapping_confidence", "inferred")

    if "category_name" in out:
        raw = out.get("category_name")
        if raw is not None and str(raw).strip() != "":
            ruled, rule_hit = _apply_category_rules(cfg, str(raw))
            canon, tier = _lookup_table(cats_tbl, ruled)
            out["canonical_category"] = canon
            out["category_mapping_confidence"] = "confirmed" if rule_hit or tier == "confirmed" else tier
        else:
            out.setdefault("canonical_category", None)
            out.setdefault("category_mapping_confidence", "inferred")

    return out


def apply_to_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if "brand_name" in r or "category_name" in r:
            out.append(apply_brand_category_canonicals(r))
        else:
            out.append(dict(r))
    return out
