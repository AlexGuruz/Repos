from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from services.common.instance import (
    default_health_path,
    legacy_health_path,
    migrate_legacy_file,
    parse_company_key_from_instance_id,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class Heartbeat:
    instance_id: str
    company_key: str
    active_years: list[int] | None
    watch_state_path: str
    posting_state_path: str
    watch_interval_secs: int
    read_only: bool = False
    posting_disabled: bool = False
    posting_disabled_reason: Optional[str] = None
    circuit_breaker_paused_until: Optional[str] = None
    circuit_breaker_consecutive_failures: int = 0
    change_detected: bool = False
    posting_attempted: bool = False
    posting_skipped_reason: Optional[str] = None

    last_tick_at: Optional[str] = None
    last_tick_duration_ms: Optional[int] = None
    last_change_detected_at: Optional[str] = None
    last_post_started_at: Optional[str] = None
    last_post_finished_at: Optional[str] = None
    last_post_ok: Optional[bool] = None
    last_post_summary: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "instance_id": self.instance_id,
            "company_key": self.company_key,
            "active_years": self.active_years,
            "watch_state_path": self.watch_state_path,
            "posting_state_path": self.posting_state_path,
            "watch_interval_secs": int(self.watch_interval_secs),
            "read_only": bool(self.read_only),
            "posting_disabled": bool(self.posting_disabled),
            "posting_disabled_reason": self.posting_disabled_reason,
            "circuit_breaker_paused_until": self.circuit_breaker_paused_until,
            "circuit_breaker_consecutive_failures": int(self.circuit_breaker_consecutive_failures or 0),
            "change_detected": bool(self.change_detected),
            "posting_attempted": bool(self.posting_attempted),
            "posting_skipped_reason": self.posting_skipped_reason,
            "last_tick_at": self.last_tick_at,
            "last_tick_duration_ms": self.last_tick_duration_ms,
            "last_change_detected_at": self.last_change_detected_at,
            "last_post_started_at": self.last_post_started_at,
            "last_post_finished_at": self.last_post_finished_at,
            "last_post_ok": self.last_post_ok,
            "last_post_summary": self.last_post_summary,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
        }


def write_heartbeat(hb: Heartbeat) -> None:
    path = default_health_path(hb.instance_id)
    migrate_legacy_file(legacy_path=legacy_health_path(hb.instance_id), new_path=path)
    payload = hb.to_dict()
    # Back-compat: keep an explicit company_key even if caller didn't provide it correctly.
    if not payload.get("company_key"):
        payload["company_key"] = parse_company_key_from_instance_id(hb.instance_id)
    payload["updated_at"] = _utc_now_iso()
    _atomic_write_json(path, payload)

