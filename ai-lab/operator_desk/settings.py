"""Load Operator Desk settings from YAML + environment overrides."""
from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import OPERATOR_CONFIG_INVALID, OperatorError
from . import paths as pathmod

_KNOWN_KEYS = frozenset(
    {
        "schema_version",
        "enabled",
        "brain_vault_root",
        "email_digest_cache_ttl_seconds",
        "growflow_snapshot_stale_seconds",
        "growflow_api_url",
        "growflow_http_timeout_seconds",
        "max_job_primer_chars",
        "bind_policy",
    }
)

_lock = threading.RLock()
_cached: "OperatorSettings | None" = None
_cached_mtime: float | None = None


@dataclass(frozen=True)
class OperatorSettings:
    schema_version: str
    enabled: bool
    brain_vault_root: Path | None
    email_digest_cache_ttl_seconds: int
    growflow_snapshot_stale_seconds: int
    growflow_api_url: str
    growflow_http_timeout_seconds: float
    max_job_primer_chars: int
    bind_policy: str


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise OperatorError(
            OPERATOR_CONFIG_INVALID,
            "PyYAML is required to load operator_settings.yaml",
        ) from exc
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except OSError as exc:
        raise OperatorError(OPERATOR_CONFIG_INVALID, f"Cannot read settings: {exc}") from exc
    except Exception as exc:  # yaml error
        raise OperatorError(OPERATOR_CONFIG_INVALID, f"Malformed settings YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise OperatorError(OPERATOR_CONFIG_INVALID, "settings root must be a mapping")
    return data


def _env_bool(name: str) -> bool | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    v = raw.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise OperatorError(OPERATOR_CONFIG_INVALID, f"Invalid boolean for {name}: {raw!r}")


def _build_settings(raw: dict[str, Any], settings_path: Path) -> OperatorSettings:
    unknown = set(raw) - _KNOWN_KEYS
    if unknown:
        raise OperatorError(
            OPERATOR_CONFIG_INVALID,
            f"Unknown settings keys: {sorted(unknown)}",
        )
    schema = str(raw.get("schema_version", "1"))
    enabled = bool(raw.get("enabled", False))
    env_enabled = _env_bool("OPERATOR_DESK_ENABLED")
    if env_enabled is not None:
        enabled = env_enabled

    brain_raw = raw.get("brain_vault_root")
    brain_path: Path | None = None
    if isinstance(brain_raw, str) and brain_raw.strip():
        brain_path = Path(brain_raw).expanduser()

    ttl = int(raw.get("email_digest_cache_ttl_seconds", 60))
    env_ttl = os.environ.get("OPERATOR_EMAIL_CACHE_TTL", "").strip()
    if env_ttl:
        ttl = int(env_ttl)

    stale = int(raw.get("growflow_snapshot_stale_seconds", 3600))
    env_stale = os.environ.get("OPERATOR_GROWFLOW_STALE_SEC", "").strip()
    if env_stale:
        stale = int(env_stale)

    api = raw.get("growflow_api_url")
    api_url = (
        str(api).strip()
        if isinstance(api, str) and api.strip()
        else os.environ.get("GROWFLOW_RETAIL_API_URL", "http://127.0.0.1:8791").rstrip("/")
    )

    timeout = float(raw.get("growflow_http_timeout_seconds", 15.0))
    max_chars = int(raw.get("max_job_primer_chars", 12000))
    bind_policy = str(raw.get("bind_policy", "loopback_only"))

    if ttl < 0 or stale < 0 or timeout <= 0 or max_chars < 500:
        raise OperatorError(OPERATOR_CONFIG_INVALID, "Numeric setting out of range")
    if bind_policy != "loopback_only":
        raise OperatorError(
            OPERATOR_CONFIG_INVALID,
            "MVP bind_policy must be loopback_only",
        )

    return OperatorSettings(
        schema_version=schema,
        enabled=enabled,
        brain_vault_root=brain_path,
        email_digest_cache_ttl_seconds=ttl,
        growflow_snapshot_stale_seconds=stale,
        growflow_api_url=api_url,
        growflow_http_timeout_seconds=timeout,
        max_job_primer_chars=max_chars,
        bind_policy=bind_policy,
    )


def get_settings(*, force_reload: bool = False) -> OperatorSettings:
    global _cached, _cached_mtime
    settings_path = pathmod.operator_settings_path()
    with _lock:
        try:
            mtime = settings_path.stat().st_mtime
        except OSError as exc:
            raise OperatorError(OPERATOR_CONFIG_INVALID, f"Missing settings file: {exc}") from exc
        if not force_reload and _cached is not None and _cached_mtime == mtime:
            return _cached
        raw = _load_yaml(settings_path)
        built = _build_settings(raw, settings_path)
        _cached = built
        _cached_mtime = mtime
        return built


def clear_settings_cache() -> None:
    global _cached, _cached_mtime
    with _lock:
        _cached = None
        _cached_mtime = None
