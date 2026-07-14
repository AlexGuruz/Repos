from __future__ import annotations

import os
import re
from typing import Any


_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    try:
        val = cfg.get(dotted_key, None)
        if val is not None:
            return val
    except Exception:
        pass
    cur = getattr(cfg, "data", cfg)
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _extract_spreadsheet_id(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    match = _SHEET_ID_RE.search(raw)
    if match:
        return match.group(1)
    if "/" not in raw and len(raw) >= 20:
        return raw
    return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the rules management workbook spreadsheet id from config or env."""
    sid = (
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
        or _cfg_get(cfg, "rules.management_spreadsheet_id")
    )
    if sid:
        return str(sid).strip() or None

    url = (
        os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL")
        or _cfg_get(cfg, "rules.management_workbook_url")
    )
    return _extract_spreadsheet_id(str(url) if url is not None else None)


__all__ = ["get_rules_management_spreadsheet_id"]
