from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            value = getter(dotted_key)
            if value is not None:
                return value
        except TypeError:
            pass
    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _spreadsheet_id_from_url(url: Any) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    match = _SPREADSHEET_ID_RE.search(text)
    if match:
        return match.group(1)
    return text if "/" not in text and len(text) >= 20 else None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the rules-management workbook id from config, URL, or env."""
    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    for value in (
        _cfg_get(cfg, "rules.management_spreadsheet_id"),
        _spreadsheet_id_from_url(_cfg_get(cfg, "rules.management_workbook_url")),
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"),
    ):
        text = str(value or "").strip()
        if text:
            return text
    return None


__all__ = ["get_rules_management_spreadsheet_id"]
