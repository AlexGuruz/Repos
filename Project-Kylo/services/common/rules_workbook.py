from __future__ import annotations

import os
from typing import Any, Optional


def _extract_spreadsheet_id(value: str) -> str:
    raw = str(value or "").strip()
    if "/spreadsheets/d/" in raw:
        try:
            return raw.split("/spreadsheets/d/", 1)[1].split("/", 1)[0]
        except Exception:
            return raw
    return raw


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if hasattr(cfg, "get"):
        try:
            return cfg.get(dotted_key, default)
        except TypeError:
            pass
    cur = cfg
    if hasattr(cfg, "data"):
        cur = getattr(cfg, "data")
    if not isinstance(cur, dict):
        return default
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def get_rules_management_spreadsheet_id(cfg: Optional[Any] = None) -> str:
    """Resolve the rules-management spreadsheet from env or Kylo config."""
    env_id = os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
    if env_id and env_id.strip():
        return _extract_spreadsheet_id(env_id)

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    cfg_id = _cfg_get(cfg, "rules.management_spreadsheet_id")
    if cfg_id and str(cfg_id).strip():
        return _extract_spreadsheet_id(str(cfg_id))

    cfg_url = _cfg_get(cfg, "rules.management_workbook_url")
    if cfg_url and str(cfg_url).strip():
        return _extract_spreadsheet_id(str(cfg_url))

    return ""


__all__ = ["get_rules_management_spreadsheet_id"]
