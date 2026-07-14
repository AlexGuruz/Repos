from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    getter = getattr(cfg, "get", None)
    if callable(getter):
        return getter(dotted_key)
    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _spreadsheet_id_from_value(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    match = _SPREADSHEET_ID_RE.search(raw)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", raw):
        return raw
    return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the rules management workbook id from config or env."""
    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    for value in (
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"),
        _cfg_get(cfg, "rules.management_spreadsheet_id"),
        _cfg_get(cfg, "rules.management_workbook_url"),
    ):
        sid = _spreadsheet_id_from_value(value)
        if sid:
            return sid
    return None


__all__ = ["get_rules_management_spreadsheet_id"]
