from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([^/?#]+)")


def extract_spreadsheet_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null"}:
        return ""

    match = _SPREADSHEET_ID_RE.search(text)
    if match:
        return match.group(1).strip()

    if "/" not in text and " " not in text:
        return text.split("#", 1)[0].split("?", 1)[0].strip()
    return ""


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None

    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            value = getter(dotted_key)
        except TypeError:
            value = getter(dotted_key, None)
        if value is not None:
            return value

    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _load_config_best_effort() -> Any:
    try:
        from services.common.config_loader import load_config

        return load_config()
    except Exception:
        return None


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str | None:
    """Resolve the rules-management workbook id from environment or Kylo config."""
    for candidate in (
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"),
        os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL"),
    ):
        spreadsheet_id = extract_spreadsheet_id(candidate)
        if spreadsheet_id:
            return spreadsheet_id

    active_cfg = cfg if cfg is not None else _load_config_best_effort()
    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        spreadsheet_id = extract_spreadsheet_id(_cfg_get(active_cfg, key))
        if spreadsheet_id:
            return spreadsheet_id
    return None


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
