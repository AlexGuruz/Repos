from __future__ import annotations

import os
from typing import Any, Optional

from services.common.config_loader import load_config


def _clean(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    return text or None


def _extract_spreadsheet_id(value: Any) -> Optional[str]:
    text = _clean(value)
    if not text:
        return None
    marker = "/spreadsheets/d/"
    if marker in text:
        return text.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0].strip() or None
    return text


def get_rules_management_spreadsheet_id(cfg: Any = None) -> Optional[str]:
    """Return the rules-management spreadsheet ID from env or Kylo config."""

    env_id = _extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = None

    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        getter = getattr(cfg, "get", None)
        value = getter(key) if callable(getter) else None
        spreadsheet_id = _extract_spreadsheet_id(value)
        if spreadsheet_id:
            return spreadsheet_id
    return None


__all__ = ["get_rules_management_spreadsheet_id"]
