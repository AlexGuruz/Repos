from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    """Read a dotted key from KyloConfig-style objects or plain nested dicts."""

    if cfg is None:
        return default

    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            value = getter(dotted_key, default)
            if value is not default:
                return value
        except Exception:
            pass

    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def extract_spreadsheet_id(value: Any) -> str | None:
    """Return a Google Sheets spreadsheet id from either an id or workbook URL."""

    text = str(value or "").strip()
    if not text:
        return None

    match = _SPREADSHEET_ID_RE.search(text)
    if match:
        return match.group(1)

    # Already an id: accept the stable character set Google uses for sheet ids.
    if re.fullmatch(r"[A-Za-z0-9_-]{20,}", text):
        return text
    return None


def _load_config_best_effort() -> Any:
    try:
        from services.common.config_loader import load_config

        return load_config()
    except Exception:
        return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the shared rules-management workbook spreadsheet id.

    Runtime env wins for operational overrides; otherwise use YAML config values.
    """

    env_id = extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    cfg = cfg if cfg is not None else _load_config_best_effort()

    configured_id = extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if configured_id:
        return configured_id

    return extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))


__all__ = [
    "extract_spreadsheet_id",
    "get_rules_management_spreadsheet_id",
]
