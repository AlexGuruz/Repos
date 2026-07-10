"""
Worker / adapter skeletons for live work orchestration (Phase 9 + Phase 10).

All collectors are read-only. No ClickUp mutations, calendar writes, or outbound sends.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from brain.prepared_context.loader import load_snapshot_fresh


class _ReadOnlyWorker(ABC):
    name: str = "base"

    @abstractmethod
    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError


class WorkDemandWorker(_ReadOnlyWorker):
    name = "work_demand"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        pa = load_snapshot_fresh("project_agenda") or {}
        rp = load_snapshot_fresh("repo_pulse") or {}
        return {"project_agenda_present": isinstance(pa, dict), "repo_pulse_present": isinstance(rp, dict)}


class TimeConstraintWorker(_ReadOnlyWorker):
    name = "time_constraint"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        po = load_snapshot_fresh("personal_ops_snapshot") or {}
        return {"personal_ops_present": isinstance(po, dict)}


class CalendarIntakeWorker(_ReadOnlyWorker):
    name = "calendar_intake"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        po = load_snapshot_fresh("personal_ops_snapshot") or {}
        data = po.get("data") if isinstance(po, dict) else {}
        ev = data.get("calendar_today") if isinstance(data, dict) else []
        return {"today_event_count": len(ev) if isinstance(ev, list) else 0, "read_only": True}


class RepoActivityWorker(_ReadOnlyWorker):
    name = "repo_activity"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        rp = load_snapshot_fresh("repo_pulse") or {}
        return {"repo_pulse_rows": len((rp.get("data") or {}).get("repos") or []) if isinstance(rp, dict) else 0}


class LocalActivityWorker(_ReadOnlyWorker):
    """Stub: Phase 11 will add local activity signals. No desktop hooks in Phase 9."""

    name = "local_activity"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"stub": True, "phase": 9, "read_only": True}


class EmailDriveIntakeWorker(_ReadOnlyWorker):
    name = "email_drive_intake"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"stub": True, "note": "Gmail/Drive adapters not wired in Phase 9", "read_only": True}


class ClickUpIntakeWorker(_ReadOnlyWorker):
    """Read-only stub for future ClickUp task/comment/status ingestion (no API in Phase 10)."""

    name = "clickup_intake"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"stub": True, "note": "ClickUp read API not called in Phase 10 foundation", "read_only": True}


class ProgressMonitorWorker(_ReadOnlyWorker):
    name = "progress_monitor"

    def collect(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        ws = load_snapshot_fresh("worker_snapshot") or {}
        return {"worker_snapshot_present": isinstance(ws, dict)}
