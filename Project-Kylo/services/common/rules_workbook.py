from __future__ import annotations

import os
from typing import Any


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def _extract_spreadsheet_id(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if "/d/" in text:
        try:
            return text.split("/d/", 1)[1].split("/", 1)[0].strip()
        except Exception:
            return text
    return text


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    getter = getattr(cfg, "get", None)
    if callable(getter):
        value = getter(dotted_key)
        if value is not None:
            return value

    cur: Any = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str | None:
    """Resolve the rules management workbook from config or environment."""
    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        sid = _extract_spreadsheet_id(_cfg_get(cfg, key))
        if sid:
            return sid

    sid = _extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    return sid or None


__all__ = ["get_rules_management_spreadsheet_id"]
