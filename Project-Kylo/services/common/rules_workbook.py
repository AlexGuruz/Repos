from __future__ import annotations

import os
from typing import Any


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    if hasattr(cfg, "get"):
        try:
            return cfg.get(dotted_key)
        except TypeError:
            pass
    cur = getattr(cfg, "data", cfg)
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _extract_spreadsheet_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    marker = "/spreadsheets/d/"
    if marker in raw:
        try:
            return raw.split(marker, 1)[1].split("/", 1)[0].strip()
        except Exception:
            return raw
    return raw


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str | None:
    """Resolve the rules-management workbook spreadsheet ID from env or config."""
    for env_name in (
        "KYLO_RULES_MANAGEMENT_SPREADSHEET_ID",
        "RULES_MANAGEMENT_SPREADSHEET_ID",
    ):
        sid = _extract_spreadsheet_id(os.environ.get(env_name))
        if sid:
            return sid

    env_url = _extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL"))
    if env_url:
        return env_url

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
    return None


__all__ = ["get_rules_management_spreadsheet_id"]
