from __future__ import annotations

import os
import re
from typing import Any


def _cfg_get(cfg: Any, dotted: str) -> Any:
    if cfg is None:
        return None
    if hasattr(cfg, "get"):
        try:
            value = cfg.get(dotted)
            if value is not None:
                return value
        except TypeError:
            pass
    cur = getattr(cfg, "data", None)
    if not isinstance(cur, dict) and isinstance(cfg, dict):
        cur = cfg
    if not isinstance(cur, dict):
        return None
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _extract_spreadsheet_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = re.search(r"/spreadsheets/d/([^/?#]+)", raw)
    if match:
        return match.group(1)
    return raw.split("/edit", 1)[0].strip()


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """Resolve the rules-management workbook from env or Kylo config."""
    for env_name in ("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "KYLO_RULES_MANAGEMENT_WORKBOOK_URL"):
        value = os.environ.get(env_name)
        sid = _extract_spreadsheet_id(value or "")
        if sid:
            return sid

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        sid = _extract_spreadsheet_id(str(_cfg_get(cfg, key) or ""))
        if sid:
            return sid
    return ""


__all__ = ["get_rules_management_spreadsheet_id"]
