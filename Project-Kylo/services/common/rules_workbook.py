from __future__ import annotations

import os
import re
from typing import Any

from services.common.config_loader import KyloConfig, load_config


_SHEETS_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9_-]+)")


def _spreadsheet_id_from_url(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    match = _SHEETS_ID_RE.search(text)
    if match:
        return match.group(1)
    if "/" not in text and len(text) >= 20:
        return text
    return None


def get_rules_management_spreadsheet_id(cfg: KyloConfig | Any | None = None) -> str | None:
    """Resolve the Rules Management workbook id without hardcoding it in consumers."""
    env_id = (os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID") or "").strip()
    if env_id:
        return env_id

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = None

    def _cfg_get(key: str) -> Any:
        if cfg is None:
            return None
        getter = getattr(cfg, "get", None)
        if callable(getter):
            return getter(key)
        if isinstance(cfg, dict):
            cur: Any = cfg
            for part in key.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    return None
            return cur
        return None

    configured_id = _cfg_get("rules.management_spreadsheet_id")
    if configured_id:
        return str(configured_id).strip() or None

    configured_url = _cfg_get("rules.management_workbook_url")
    if configured_url:
        return _spreadsheet_id_from_url(str(configured_url))

    return None


__all__ = ["get_rules_management_spreadsheet_id"]
