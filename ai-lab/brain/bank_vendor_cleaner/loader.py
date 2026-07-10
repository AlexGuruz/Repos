from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from brain.bank_vendor_cleaner.paths import (
    ai_lab_root,
    default_alias_map_path,
    default_cleaning_rules_path,
    default_manifest_path,
    default_overrides_path,
    default_rejected_aliases_path,
    default_vendor_lookup_cache_path,
    default_vendor_lookup_providers_path,
    default_vendor_lookup_rules_path,
)


def resolve_config_path(path: str | Path | None) -> Path | None:
    if path is None:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = ai_lab_root() / p
    return p


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_alias_map(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or default_alias_map_path())


def load_cleaning_rules(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or default_cleaning_rules_path())


def load_manifest(path: Path | None = None) -> dict[str, Any]:
    return load_json(path or default_manifest_path())


def load_city_state_overrides(path: Path | None = None) -> dict[str, Any]:
    p = path or default_overrides_path()
    if not p.is_file():
        return {}
    return load_yaml(p)


def load_rejected_aliases(path: Path | None = None) -> list[str]:
    p = path or default_rejected_aliases_path()
    if not p.is_file():
        return []
    data = load_yaml(p)
    patterns = data.get("rejected_patterns")
    return list(patterns) if isinstance(patterns, list) else []


def load_vendor_lookup_rules(path: Path | None = None) -> dict[str, Any]:
    p = path or default_vendor_lookup_rules_path()
    if not p.is_file():
        return {"enabled": False}
    return load_yaml(p)


def load_vendor_lookup_cache(path: Path | None = None) -> dict[str, Any]:
    p = path or default_vendor_lookup_cache_path()
    if not p.is_file():
        return {"version": 1, "entries": [], "pending": []}
    return load_yaml(p)


def load_vendor_lookup_providers(path: Path | None = None) -> dict[str, Any]:
    p = path or default_vendor_lookup_providers_path()
    if not p.is_file():
        return {"version": 1, "providers": {}}
    return load_yaml(p)
