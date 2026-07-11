from __future__ import annotations

from pathlib import Path

from services.common.instance import instance_logs_dir, instance_root, instance_state_dir


def audit_log_path(instance_id: str) -> Path:
    return instance_logs_dir(instance_id) / "audit.log"


def audit_jsonl_path(instance_id: str) -> Path:
    return instance_logs_dir(instance_id) / "audit.jsonl"


def row_registry_path(instance_id: str) -> Path:
    return instance_state_dir(instance_id) / "row_registry.json"


def business_line_registry_path(instance_id: str) -> Path:
    return instance_state_dir(instance_id) / "business_line_registry.json"


def revision_state_path(instance_id: str) -> Path:
    return instance_state_dir(instance_id) / "audit_revision_state.json"


def snapshots_root(instance_id: str) -> Path:
    return instance_root(instance_id) / "snapshots"


def latest_snapshot_link(instance_id: str) -> Path:
    return instance_root(instance_id) / "snapshots_latest"


__all__ = [
    "audit_jsonl_path",
    "audit_log_path",
    "business_line_registry_path",
    "latest_snapshot_link",
    "revision_state_path",
    "row_registry_path",
    "snapshots_root",
]
