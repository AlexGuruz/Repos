"""Rules-management workbook helpers."""
from __future__ import annotations

import os
import re
from typing import Any


_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            value = getter(dotted_key, default)
            if value is not None:
                return value
        except Exception:
            pass
    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _spreadsheet_id_from_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _SHEET_ID_RE.search(text)
    if match:
        return match.group(1)
    if "/" not in text and len(text) >= 20:
        return text
    return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the rules-management spreadsheet id from env/config.

    Accepts both the normalized ``KyloConfig`` wrapper and plain nested dicts so
    import-time callers and tests do not need to agree on one config shape.
    """
    direct = _spreadsheet_id_from_value(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if direct:
        return direct

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    direct = _spreadsheet_id_from_value(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if direct:
        return direct

    url = _cfg_get(cfg, "rules.management_workbook_url") or os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL")
    return _spreadsheet_id_from_value(url)


__all__ = ["get_rules_management_spreadsheet_id"]
