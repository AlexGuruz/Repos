from __future__ import annotations

import json
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from config.schema import KyloConfigModel


def _default_config_path() -> str:
    return os.environ.get("KYLO_CONFIG_PATH", os.path.join("config", "kylo.config.yaml"))


def _default_env_path() -> str:
    return os.environ.get("KYLO_ENV_PATH", ".env")


@dataclass
class KyloConfig:
    data: Dict[str, Any]
    model: KyloConfigModel

    def get(self, dotted_key: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def _load_yaml(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML not installed; add pyyaml to requirements to use kylo.config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise RuntimeError("Invalid YAML root (expected mapping)")
    return raw


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-merge two mappings.

    Rules:
      - Scalars: override wins
      - Dicts: recursively merge
      - Lists: override replaces base (no implicit union)
    """
    out: Dict[str, Any] = dict(base)
    for k, v in (override or {}).items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _parse_company_key_from_instance_id(instance_id: str) -> str:
    # Accept formats like:
    # - JGD_2025
    # - JGD:2025
    # - JGD
    raw = (instance_id or "").strip()
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    if "_" in raw:
        raw = raw.split("_", 1)[0]
    return raw.strip().upper()


def _layered_paths(base_dir: Path, instance_id: str) -> Tuple[Path, Path, Path]:
    """Return (global, company, instance) config file paths."""
    global_path = base_dir / "global.yaml"
    company_key = _parse_company_key_from_instance_id(instance_id)
    company_path = base_dir / "companies" / f"{company_key}.yaml"
    instance_path = base_dir / "instances" / f"{instance_id}.yaml"
    return global_path, company_path, instance_path


def _load_layered_config(base_dir: Path, instance_id: str) -> Dict[str, Any]:
    """Load config as global -> company -> instance (deterministic merge)."""
    global_path, company_path, instance_path = _layered_paths(base_dir, instance_id)

    # Load instance first (if present) so it can override company_key selection.
    instance_raw: Dict[str, Any] = {}
    if instance_path.exists():
        instance_raw = _load_yaml(str(instance_path))

    # Optional override: instance.company_key
    company_key_override = (
        (instance_raw.get("instance") or {}).get("company_key")
        if isinstance(instance_raw.get("instance"), dict)
        else None
    )
    company_path_effective = company_path
    if company_key_override:
        company_path_effective = base_dir / "companies" / f"{str(company_key_override).strip().upper()}.yaml"

    global_raw: Dict[str, Any] = _load_yaml(str(global_path)) if global_path.exists() else {}
    company_raw: Dict[str, Any] = _load_yaml(str(company_path_effective)) if company_path_effective.exists() else {}

    merged = _deep_merge(global_raw, company_raw)
    merged = _deep_merge(merged, instance_raw)
    return merged


def _load_env_file(env_path: Optional[str]) -> None:
    """Load key/value pairs from a dotenv-style file into os.environ.

    Existing environment variables win; we only set values that are currently unset.
    This keeps runtime overrides intact while enabling local development defaults.
    """

    if not env_path:
        return
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#"):
                    continue
                if "=" not in text:
                    continue
                key, value = text.split("=", 1)
                key = key.strip()
                if not key or key in os.environ:
                    continue
                os.environ[key] = value.strip().strip('"').strip("'")
    except Exception:
        # Dotenv loading is best-effort; ignore parse errors to avoid breaking runtime.
        pass


def _fallback_from_env_and_files() -> Dict[str, Any]:
    # Minimal fallback using existing envs and companies.json
    cfg: Dict[str, Any] = {
        "runtime": {
            "dry_run": os.environ.get("KYLO_SHEETS_DRY_RUN", "true").lower() in ("1", "true", "yes", "y"),
            "log_level": os.environ.get("KYLO_LOG_LEVEL", "INFO"),
            "timezone": os.environ.get("KYLO_TIMEZONE", "America/Chicago"),
        },
        "google": {
            "service_account_json_path": os.environ.get(
                "GOOGLE_SERVICE_ACCOUNT",
                os.path.join(os.environ.get("KYLO_SECRETS_DIR", "secrets"), "service_account.json"),
            ),
        },
        "database": {
            "global_dsn": os.environ.get("KYLO_GLOBAL_DSN", "postgresql://postgres:kylo@localhost:5433/kylo_global"),
            "per_company": False,
            "company_dsns": json.loads(os.environ.get("KYLO_DB_DSN_MAP", "{}")),
        },
    }
    # Populate sheets.companies from config/companies.json if present
    try:
        companies_path = os.path.join("config", "companies.json")
        if os.path.exists(companies_path):
            with open(companies_path, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            items = data.get("companies") or []
            companies = []
            for it in items:
                cid = (it.get("company_id") or "").strip().upper()
                url = (it.get("workbook") or "").split("/edit")[0]
                if cid and url:
                    companies.append(
                        {
                            "key": "710" if cid == "710 EMPIRE" else cid.replace(" ", ""),
                            "workbook_url": url,
                            "tabs": {"intake": "PETTY CASH", "output": "CLEAN TRANSACTIONS"},
                        }
                    )
            if companies:
                cfg.setdefault("sheets", {})["companies"] = companies
    except Exception:
        pass
    return cfg


def load_config(path: Optional[str] = None) -> KyloConfig:
    """Load the Kylo configuration and return a helper wrapper."""

    # Load dotenv-style file first so downstream config values can reference it.
    _load_env_file(_default_env_path())

    # If an explicit file path is provided, preserve the legacy "single file" behavior.
    if path:
        if os.path.exists(path):
            data = _load_yaml(path)
        else:
            data = _fallback_from_env_and_files()
        model = KyloConfigModel.model_validate(data)
        normalized = model.model_dump(mode="python")
        return KyloConfig(data=normalized, model=model)

    instance_id = (os.environ.get("KYLO_INSTANCE_ID") or "").strip()
    default_path = _default_config_path()

    # Layered resolution (global -> company -> instance) when KYLO_INSTANCE_ID is set
    # and config/global.yaml exists.
    if instance_id:
        base_dir = Path("config")
        # If KYLO_CONFIG_PATH points to global.yaml, treat its parent as the base directory.
        if default_path and os.path.splitext(default_path)[1].lower() in (".yaml", ".yml"):
            p = Path(default_path)
            if p.name.lower() == "global.yaml":
                base_dir = p.parent
        global_path = base_dir / "global.yaml"
        if global_path.exists():
            data = _load_layered_config(base_dir=base_dir, instance_id=instance_id)
            # Fresh-rig override: use project .secrets if KYLO_SECRETS_DIR is set
            if os.environ.get("KYLO_SECRETS_DIR"):
                sa_path = os.path.join(os.environ["KYLO_SECRETS_DIR"], "service_account.json")
                data.setdefault("google", {})["service_account_json_path"] = sa_path
            model = KyloConfigModel.model_validate(data)
            normalized = model.model_dump(mode="python")
            return KyloConfig(data=normalized, model=model)

    # Default legacy file behavior.
    if os.path.exists(default_path):
        data = _load_yaml(default_path)
    else:
        data = _fallback_from_env_and_files()
    # Fresh-rig override: use project .secrets if KYLO_SECRETS_DIR is set
    if os.environ.get("KYLO_SECRETS_DIR"):
        sa_path = os.path.join(os.environ["KYLO_SECRETS_DIR"], "service_account.json")
        data.setdefault("google", {})["service_account_json_path"] = sa_path

    model = KyloConfigModel.model_validate(data)
    normalized = model.model_dump(mode="python")
    return KyloConfig(data=normalized, model=model)


__all__ = ["KyloConfig", "load_config"]


