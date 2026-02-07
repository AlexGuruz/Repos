from __future__ import annotations

import os
import shutil
from pathlib import Path


def get_instance_id() -> str | None:
    """Return the current instance_id if set."""
    val = (os.environ.get("KYLO_INSTANCE_ID") or "").strip()
    return val or None


def get_watcher_name() -> str | None:
    """Prefer WATCHER_NAME; fallback to KYLO_INSTANCE_ID."""
    name = (os.environ.get("WATCHER_NAME") or "").strip()
    if name:
        return name
    return get_instance_id()


def instance_root(instance_id: str) -> Path:
    return Path(".kylo") / "instances" / instance_id


def instance_logs_dir(instance_id: str) -> Path:
    return instance_root(instance_id) / "logs"


def instance_state_dir(instance_id: str) -> Path:
    return instance_root(instance_id) / "state"


def instance_health_dir(instance_id: str) -> Path:
    return instance_root(instance_id) / "health"


def instance_tmp_dir(instance_id: str) -> Path:
    return instance_root(instance_id) / "tmp"


def instance_queue_dir(instance_id: str) -> Path:
    return instance_root(instance_id) / "queue"


def default_watch_state_path(instance_id: str) -> Path:
    return instance_state_dir(instance_id) / "watch_state.json"


def default_posting_state_path(instance_id: str) -> Path:
    return instance_state_dir(instance_id) / "posting_state.json"


def default_health_path(instance_id: str) -> Path:
    return instance_health_dir(instance_id) / "heartbeat.json"


def default_watcher_log_path(instance_id: str) -> Path:
    return instance_logs_dir(instance_id) / "watcher.log"


def legacy_watch_state_path(instance_id: str) -> Path:
    return Path(".kylo") / f"watch_state_{instance_id}.json"


def legacy_posting_state_path(instance_id: str) -> Path:
    return Path(".kylo") / f"state_{instance_id}.json"


def legacy_health_path(instance_id: str) -> Path:
    return Path(".kylo") / "health" / f"{instance_id}.json"


def migrate_legacy_file(*, legacy_path: Path, new_path: Path) -> None:
    """Best-effort migration from legacy single-file layout to per-instance dirs.

    We copy (not move) to avoid surprises; the new path is the source of truth after migration.
    """
    try:
        if new_path.exists():
            return
        if not legacy_path.exists():
            return
        new_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_path, new_path)
    except Exception:
        return


def parse_company_key_from_instance_id(instance_id: str) -> str:
    """Extract company key from an instance id like JGD_2025 or JGD:2025."""
    raw = (instance_id or "").strip()
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    if "_" in raw:
        raw = raw.split("_", 1)[0]
    return raw.strip().upper()

