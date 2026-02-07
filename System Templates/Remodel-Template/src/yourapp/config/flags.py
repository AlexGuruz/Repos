"""
Feature flags and configuration helpers.

Reads configuration from environment variables with sensible defaults.
"""
import os
from typing import Set


def _bool(name: str, default: bool) -> bool:
    """Read boolean environment variable."""
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _str(name: str, default: str) -> str:
    """Read string environment variable."""
    return os.getenv(name, default)


def _csv(name: str) -> Set[str]:
    """Read comma-separated environment variable as set."""
    raw = os.getenv(name, "") or ""
    return set([x.strip() for x in raw.split(",") if x.strip()])


def _int(name: str, default: int) -> int:
    """Read integer environment variable."""
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    """Read float environment variable."""
    v = os.getenv(name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


# Multi-Schema Configuration
def multi_schema_enabled() -> bool:
    """Controls whether multi-schema mode is enabled (single DSN + per-entity schemas)."""
    return _bool("APP_MULTI_SCHEMA", False)


def entity_schema_prefix() -> str:
    """Prefix for entity schema names (e.g., 'app_' for app_entity1, app_entity2, etc.)."""
    return _str("APP_ENTITY_SCHEMA_PREFIX", "app_")


def global_dsn() -> str:
    """Global DSN for multi-schema mode (replaces per-entity DSNs)."""
    return _str("APP_GLOBAL_DSN", "")


def entity_schemas() -> dict:
    """Entity ID to schema name mapping."""
    raw = _str("APP_ENTITY_SCHEMAS", "entity1:app_entity1,entity2:app_entity2")
    if not raw:
        return {}
    
    schema_map = {}
    for pair in raw.split(","):
        if ":" in pair:
            entity_id, schema_name = pair.split(":", 1)
            schema_map[entity_id.strip()] = schema_name.strip()
    return schema_map


def shadow_mode_enabled() -> bool:
    """Controls whether shadow mode is enabled for multi-schema validation."""
    return _bool("APP_SHADOW_MODE", False)


def shadow_schema_suffix() -> str:
    """Suffix for shadow schemas (e.g., '_shadow' for app_entity1_shadow)."""
    return _str("APP_SHADOW_SCHEMA_SUFFIX", "_shadow")


# Retry Configuration
def max_retry_attempts() -> int:
    """Maximum number of retry attempts for failed operations."""
    return _int("APP_MAX_RETRY_ATTEMPTS", 3)


def base_retry_delay_ms() -> int:
    """Base delay for exponential backoff in milliseconds."""
    return _int("APP_BASE_RETRY_DELAY_MS", 1000)


def max_retry_delay_ms() -> int:
    """Maximum delay for exponential backoff in milliseconds."""
    return _int("APP_MAX_RETRY_DELAY_MS", 30000)
