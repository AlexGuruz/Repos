"""Load configuration from config.yaml."""
import os
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent

# Device-wide service account (no per-repo copy needed)
_DEFAULT_CREDS_PATHS = [
    Path("D:/_config/google_service_account.json"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "_config" / "google_service_account.json",
]


def get_service_account_path() -> Path | None:
    """
    Resolve service account JSON path. Order:
    1. config.yaml service_account_path (if set and exists)
    2. GOOGLE_APPLICATION_CREDENTIALS env var
    3. D:\\_config\\google_service_account.json
    """
    cfg = load_config()
    cfg_path = cfg.get("google_sheets", {}).get("service_account_path")
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        if p.exists():
            return p
    env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env:
        p = Path(env)
        if p.exists():
            return p
    for d in _DEFAULT_CREDS_PATHS:
        if d.exists():
            return d
    return None


def load_config():
    """Load config from config/config.yaml."""
    config_path = _PROJECT_ROOT / "config" / "config.yaml"
    if not config_path.exists():
        config_path = _PROJECT_ROOT / "config" / "config.example.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_path(key: str, default: str = "") -> Path:
    """Resolve a path from config, relative to project root."""
    cfg = load_config()
    paths = cfg.get("paths", {})
    val = paths.get(key, default)
    if not val:
        return _PROJECT_ROOT
    p = Path(val)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    return p


def get_drive_folder_id() -> str:
    """Get the Google Drive watch folder ID."""
    cfg = load_config()
    return cfg.get("google_drive", {}).get(
        "watch_folder_id", "1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP"
    )
