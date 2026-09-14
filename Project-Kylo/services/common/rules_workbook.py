from __future__ import annotations

import os
from typing import Any


def extract_spreadsheet_id(value: Any) -> str:
    """Return a Google Sheets spreadsheet ID from a raw ID or spreadsheet URL."""
    text = str(value or "").strip()
    if not text:
        return ""
    marker = "/spreadsheets/d/"
    if marker in text:
        try:
            return text.split(marker, 1)[1].split("/", 1)[0].strip()
        except Exception:
            return text
    return text


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str:
    """Resolve the rules-management workbook spreadsheet ID.

    The explicit environment override is useful for workers where the
    management workbook is injected outside the YAML config.
    """
    env_value = os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
    if env_value:
        return extract_spreadsheet_id(env_value)

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        try:
            value = cfg.get(key) if cfg is not None else None
        except Exception:
            value = None
        spreadsheet_id = extract_spreadsheet_id(value)
        if spreadsheet_id:
            return spreadsheet_id

    return ""


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
