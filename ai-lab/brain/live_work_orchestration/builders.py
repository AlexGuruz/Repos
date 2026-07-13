"""
Snapshot builders for live work orchestration (Phase 9–12).

Writes JSON under state/live_work_orchestration/. Read-only inputs from prepared context.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso
from brain.prepared_context.store import load_snapshot

from brain.live_work_orchestration.workers import (
    CalendarIntakeWorker,
    ClickUpIntakeWorker,
    EmailDriveIntakeWorker,
    LocalActivityWorker,
    ProgressMonitorWorker,
    RepoActivityWorker,
    TimeConstraintWorker,
    WorkDemandWorker,
)


def live_work_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    d = root / "state" / "live_work_orchestration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _evidence(title: str, summary: str, path: str | None = None) -> dict[str, Any]:
    return {
        "title": title,
        "summary": summary,
        "source_path_or_tool": path,
        "observed_at": now_iso(),
        "confidence": 0.75,
    }


def _wrap(
    snapshot_type: str,
    *,
    data: dict[str, Any],
    missing_sources: list[str],
    evidence_items: list[dict[str, Any]],
    confidence: float,
    sources: list[str],
    summary_short: str,
    summary_detailed: str,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "snapshot_type": snapshot_type,
        "generated_at": now_iso(),
        "stale": False,
        "confidence": float(confidence),
        "source_files_or_tools": sources,
        "missing_sources": missing_sources,
        "errors": list(errors or []),
        "data": data,
        "summary_short": summary_short,
        "summary_detailed": summary_detailed,
        "evidence_items": evidence_items,
        "suggested_questions": [],
    }


def _write(name: str, payload: dict[str, Any]) -> Path:
    p = live_work_dir() / f"{name}.json"
    p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return p


def _load_ingestion_snapshot(name: str) -> dict[str, Any] | None:
    p = live_work_dir() / "ingestion" / f"{name}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_work_demand_snapshot() -> dict[str, Any]:
    missing: list[str] = []
    sources: list[str] = ["prepared_context:project_agenda", "prepared_context:repo_pulse"]
    pa = load_snapshot("project_agenda")
    rp = load_snapshot("repo_pulse")
    if not pa:
        missing.append("project_agenda")
    if not rp:
        missing.append("repo_pulse")
    demands: list[dict[str, Any]] = []
    if isinstance(pa, dict):
        d = pa.get("data") or {}
        for i, line in enumerate((d.get("today_focus") or [])[:12]):
            demands.append(
                {
                    "id": f"wd-today-{i}",
                    "source": "project_agenda.today_focus",
                    "confidence": 0.7 if not missing else 0.4,
                    "observed_at": pa.get("generated_at", now_iso()),
                    "created_at": now_iso(),
                    "notes": str(line),
                    "evidence": ["project_agenda"],
                    "status": "open",
                    "title": str(line),
                    "project_hint": str(line),
                }
            )
        for i, line in enumerate((d.get("next_actions") or [])[:12]):
            demands.append(
                {
                    "id": f"wd-next-{i}",
                    "source": "project_agenda.next_actions",
                    "confidence": 0.65,
                    "observed_at": pa.get("generated_at", now_iso()),
                    "created_at": now_iso(),
                    "notes": str(line),
                    "evidence": ["project_agenda"],
                    "status": "open",
                    "title": str(line),
                    "project_hint": "",
                }
            )
    if isinstance(rp, dict):
        for i, row in enumerate((rp.get("data") or {}).get("repos") or []):
            if not isinstance(row, dict):
                continue
            if not row.get("readme_fresh") or row.get("stale"):
                demands.append(
                    {
                        "id": f"wd-repo-{i}",
                        "source": "repo_pulse",
                        "confidence": 0.55,
                        "observed_at": rp.get("generated_at", now_iso()),
                        "created_at": now_iso(),
                        "notes": f"Repo maintenance signal: {row.get('repo')}",
                        "evidence": ["repo_pulse"],
                        "status": "open",
                        "title": f"Attention: {row.get('repo')}",
                        "project_hint": str(row.get("repo") or ""),
                    }
                )
    ev = [
        _evidence("Work demand snapshot", f"{len(demands)} demand rows synthesized", "project_agenda"),
    ]
    snap = _wrap(
        "work_demand_snapshot",
        data={"demands": demands, "worker_probe": WorkDemandWorker().collect()},
        missing_sources=missing,
        evidence_items=ev,
        confidence=0.72 if not missing else 0.45,
        sources=sources,
        summary_short=f"Work demands: {len(demands)} items (read-only)",
        summary_detailed="Synthesized from project_agenda and repo_pulse only; live ClickUp/GitHub not queried in Phase 9.",
    )
    _write("work_demand_snapshot", snap)
    return snap


def build_time_constraints_snapshot() -> dict[str, Any]:
    missing: list[str] = []
    sources = ["prepared_context:personal_ops_snapshot", "prepared_context:system_snapshot"]
    po = load_snapshot("personal_ops_snapshot")
    ss = load_snapshot("system_snapshot")
    if not po:
        missing.append("personal_ops_snapshot")
    if not ss:
        missing.append("system_snapshot")
    constraints: list[dict[str, Any]] = []
    if isinstance(po, dict):
        d = po.get("data") or {}
        for i, ev in enumerate((d.get("calendar_today") or [])[:20]):
            if not isinstance(ev, dict):
                continue
            constraints.append(
                {
                    "id": f"tc-cal-{i}",
                    "source": "personal_ops.calendar_today",
                    "confidence": 0.8,
                    "observed_at": po.get("generated_at", now_iso()),
                    "created_at": now_iso(),
                    "notes": str(ev.get("summary") or ev),
                    "evidence": ["personal_ops_snapshot"],
                    "status": "open",
                    "label": "calendar",
                    "window_hint": str(ev.get("start") or ""),
                }
            )
        if not constraints and not (d.get("calendar_today") or []):
            constraints.append(
                {
                    "id": "tc-no-calendar",
                    "source": "personal_ops",
                    "confidence": 0.3,
                    "observed_at": po.get("generated_at", now_iso()),
                    "created_at": now_iso(),
                    "notes": "No calendar events in snapshot; do not invent meetings.",
                    "evidence": [],
                    "status": "open",
                    "label": "gap",
                    "window_hint": "",
                }
            )
    if isinstance(ss, dict):
        constraints.append(
            {
                "id": "tc-system",
                "source": "system_snapshot",
                "confidence": 0.5,
                "observed_at": ss.get("generated_at", now_iso()),
                "created_at": now_iso(),
                "notes": "System / ops context available for shift boundary hints only.",
                "evidence": ["system_snapshot"],
                "status": "open",
                "label": "system",
                "window_hint": "",
            }
        )
    snap = _wrap(
        "time_constraints_snapshot",
        data={"constraints": constraints, "worker_probe": TimeConstraintWorker().collect()},
        missing_sources=missing,
        evidence_items=[_evidence("Time constraints", f"{len(constraints)} rows")],
        confidence=0.68 if not missing else 0.42,
        sources=sources,
        summary_short=f"Time constraints: {len(constraints)} rows",
        summary_detailed="Calendar + system snapshot only; no calendar writes.",
    )
    _write("time_constraints_snapshot", snap)
    return snap


def build_daily_progress_snapshot() -> dict[str, Any]:
    sources = [
        "prepared_context:worker_snapshot",
        "prepared_context:repo_pulse",
        "workers:read_only_probe",
        "ingestion:repo_activity_snapshot",
        "ingestion:github_activity_snapshot",
        "ingestion:bills_snapshot",
    ]
    missing: list[str] = []
    ws = load_snapshot("worker_snapshot")
    if not ws:
        missing.append("worker_snapshot")
    repo_ingestion = _load_ingestion_snapshot("repo_activity_snapshot")
    if not repo_ingestion:
        missing.append("repo_activity_snapshot")
    github_ingestion = _load_ingestion_snapshot("github_activity_snapshot")
    if not github_ingestion:
        missing.append("github_activity_snapshot")
    bills_ingestion = _load_ingestion_snapshot("bills_snapshot")
    if not bills_ingestion:
        missing.append("bills_snapshot")
    from brain.live_work_orchestration.ingestion.bills import summarize_bills_for_planning

    bills_planning = summarize_bills_for_planning(bills_ingestion)
    events: list[dict[str, Any]] = []
    if isinstance(ws, dict):
        events.append(
            {
                "id": "pe-worker",
                "source": "worker_snapshot",
                "confidence": 0.55,
                "observed_at": ws.get("generated_at", now_iso()),
                "created_at": now_iso(),
                "notes": "Worker health / reachability summary (read-only).",
                "evidence": ["worker_snapshot"],
                "status": "done",
                "metric": "worker_snapshot_loaded",
                "source_type": "repo",
            }
        )
    repo_activity_rows: list[dict[str, Any]] = []
    repo_activity_events: list[dict[str, Any]] = []
    github_feature_states: list[dict[str, Any]] = []
    github_blockers: list[dict[str, Any]] = []
    github_remote_summary: dict[str, Any] = {}
    if isinstance(repo_ingestion, dict):
        data = repo_ingestion.get("data") if isinstance(repo_ingestion.get("data"), dict) else {}
        repo_activity_rows = list(data.get("activity") or [])
        for i, ev in enumerate(list(data.get("progress_events") or [])):
            if not isinstance(ev, dict):
                continue
            events.append(
                {
                    "id": f"pe-repo-{i}",
                    "source": "repo_activity_ingestion",
                    "confidence": float(ev.get("confidence") or repo_ingestion.get("confidence") or 0.5),
                    "observed_at": str(ev.get("observed_at") or repo_ingestion.get("generated_at") or now_iso()),
                    "created_at": now_iso(),
                    "notes": str(ev.get("summary") or ""),
                    "evidence": list(ev.get("evidence") or []),
                    "status": "done",
                    "metric": str(ev.get("activity_intensity") or "repo_activity"),
                    "source_type": "repo",
                }
            )
            repo_activity_events.append(ev)
    if isinstance(github_ingestion, dict):
        g_data = github_ingestion.get("data") if isinstance(github_ingestion.get("data"), dict) else {}
        github_feature_states = list(g_data.get("feature_states") or [])
        github_remote_summary = dict(g_data.get("correlation_summary") or {})
        for i, fs in enumerate(github_feature_states):
            if not isinstance(fs, dict):
                continue
            blockers = list(fs.get("blockers") or [])
            if blockers:
                github_blockers.append(
                    {
                        "feature_name": fs.get("feature_name"),
                        "repo_name": fs.get("repo_name"),
                        "blockers": blockers,
                    }
                )
            events.append(
                {
                    "id": f"pe-gh-{i}",
                    "source": "github_activity_ingestion",
                    "confidence": float(fs.get("confidence") or github_ingestion.get("confidence") or 0.6),
                    "observed_at": str(github_ingestion.get("generated_at") or now_iso()),
                    "created_at": now_iso(),
                    "notes": (
                        f"{fs.get('repo_name')}::{fs.get('feature_name')} stage={fs.get('rollout_stage')} "
                        f"local={fs.get('local_activity_present')} blockers={len(blockers)}"
                    ),
                    "evidence": list(fs.get("evidence") or []),
                    "status": "done",
                    "metric": str(fs.get("rollout_stage") or "github_activity"),
                    "source_type": "repo",
                }
            )
    snap = _wrap(
        "daily_progress_snapshot",
        data={
            "events": events,
            "worker_probe": ProgressMonitorWorker().collect(),
            "repo_probe": RepoActivityWorker().collect(),
            "repo_activity_ingestion_summary": (repo_ingestion or {}).get("data", {}).get("summary", {}),
            "repo_activity_rows": repo_activity_rows,
            "repo_activity_events": repo_activity_events,
            "github_feature_states": github_feature_states,
            "github_remote_summary": github_remote_summary,
            "github_blockers": github_blockers,
            "local_activity_probe": LocalActivityWorker().collect(),
            "bills_upcoming": bills_planning.get("upcoming") or [],
            "bills_overdue": bills_planning.get("overdue") or [],
            "bills_high_risk": bills_planning.get("high_risk") or [],
            "bills_warnings": bills_planning.get("warnings") or [],
            "bills_clarification_proposals": bills_planning.get("clarifications") or [],
        },
        missing_sources=missing,
        evidence_items=[
            _evidence("Progress", f"{len(events)} events"),
            _evidence(
                "Repo activity ingestion",
                f"{len(repo_activity_events)} repo activity signals",
                "state/live_work_orchestration/ingestion/repo_activity_snapshot.json",
            ),
            *[
                _evidence(
                    f"Repo timestamps: {row.get('repo_name')}",
                    (
                        f"activity_window_start={row.get('activity_window_start')} "
                        f"activity_window_end={row.get('activity_window_end')} | "
                        f"git_hygiene_summary={row.get('git_hygiene_summary')} | "
                        f"commit_needed={row.get('commit_needed')} push_needed={row.get('push_needed')}"
                    ),
                    "state/live_work_orchestration/ingestion/repo_activity_snapshot.json",
                )
                for row in repo_activity_rows[:12]
                if isinstance(row, dict)
            ],
            _evidence(
                "GitHub activity ingestion",
                f"{len(github_feature_states)} feature state signals",
                "state/live_work_orchestration/ingestion/github_activity_snapshot.json",
            ),
            _evidence(
                "Bills / financial obligations",
                (bills_ingestion or {}).get("summary_detailed") or "No bills snapshot on disk",
                "state/live_work_orchestration/ingestion/bills_snapshot.json",
            ),
        ],
        confidence=0.72 if (repo_ingestion and github_ingestion) else (0.62 if repo_ingestion else 0.55),
        sources=sources,
        summary_short=f"Daily progress: {len(events)} events; bills {len(bills_planning.get('overdue') or [])} overdue",
        summary_detailed=(
            "Read-only progress combines worker probes, local git metadata, and GitHub PR/issue states; "
            "financial obligations surfaced from bills_snapshot when present (no payment actions)."
        ),
    )
    _write("daily_progress_snapshot", snap)
    return snap


def build_communication_queue_snapshot() -> dict[str, Any]:
    """ClickUp-facing clarification queue snapshot (read-only; no outbound sends)."""
    from brain.live_work_orchestration.clickup_queue import list_clarification_items

    pending = [x for x in list_clarification_items() if x.get("status") in ("queued", "active")]
    snap = _wrap(
        "communication_queue_snapshot",
        data={
            "items": pending,
            "queue_role": "clickup_clarification_pending",
            "probes": {
                "clickup": ClickUpIntakeWorker().collect(),
                "email_drive": EmailDriveIntakeWorker().collect(),
            },
        },
        missing_sources=["clickup_live_read", "gmail_api"],
        evidence_items=[_evidence("Communication queue", "ClickUp clarification queue — local state only until approval")],
        confidence=0.9,
        sources=["stubs_only", "clickup_clarification_queue.json"],
        summary_short="ClickUp clarification queue snapshot (read-only)",
        summary_detailed="One active clarification at a time; proposals enqueue with approval; no automatic ClickUp posts.",
    )
    _write("communication_queue_snapshot", snap)
    return snap


def build_clickup_action_snapshot() -> dict[str, Any]:
    """Optional aggregate of pending ClickUp action proposals (local JSON only)."""
    from brain.live_work_orchestration.clickup_queue import get_action_queue_document

    doc = get_action_queue_document()
    items = list(doc.get("items") or [])
    snap = _wrap(
        "clickup_action_snapshot",
        data={
            "items": items,
            "pending_count": len([x for x in items if str(x.get("status")) == "queued"]),
        },
        missing_sources=["clickup_live_read"],
        evidence_items=[_evidence("ClickUp actions", f"{len(items)} queued/preview rows (no execution)")],
        confidence=0.85,
        sources=["clickup_action_queue.json"],
        summary_short="ClickUp action queue mirror (read-only)",
        summary_detailed="Task/comment/status proposals only; execution requires approval pipeline.",
    )
    _write("clickup_action_snapshot", snap)
    return snap


def build_timetable_snapshot() -> dict[str, Any]:
    """Optional Phase 13 timetable snapshot derived from local + GitHub ingestion."""
    from brain.live_work_orchestration.compiler import generate_project_timetable

    payload = generate_project_timetable(enqueue_clarifications=False)
    snap = _wrap(
        "timetable_snapshot",
        data=payload,
        missing_sources=[],
        evidence_items=[_evidence("Project timetable", "Range-based feature estimates with guardrails")],
        confidence=0.7,
        sources=["ingestion/repo_activity_snapshot.json", "ingestion/github_activity_snapshot.json"],
        summary_short="Project timetable snapshot (read-only)",
        summary_detailed="Guardrail-enforced ranges only; unknown when evidence is insufficient.",
    )
    _write("timetable_snapshot", snap)
    return snap


def build_planning_gaps_snapshot() -> dict[str, Any]:
    wd = load_snapshot("work_demand_snapshot")  # may not exist first run — use live dir file after build order
    # This builder runs after others in build_all; still compute from prepared context
    missing_inputs: list[dict[str, Any]] = []
    inv_path = Path(__file__).resolve().parents[2] / "state" / "integration_inventory" / "summary.json"
    if not inv_path.is_file():
        missing_inputs.append(
            {
                "id": "gap-inv",
                "source": "integration_inventory",
                "confidence": 1.0,
                "observed_at": now_iso(),
                "created_at": now_iso(),
                "notes": "integration_inventory summary not found",
                "evidence": [],
                "status": "open",
                "gap_type": "integration_inventory_missing",
            }
        )
    snap = _wrap(
        "planning_gaps_snapshot",
        data={"gaps": missing_inputs},
        missing_sources=[g["gap_type"] for g in missing_inputs] if missing_inputs else [],
        evidence_items=[_evidence("Planning gaps", f"{len(missing_inputs)} gap(s) reported, not guessed")],
        confidence=0.85,
        sources=["state/integration_inventory/summary.json"],
        summary_short="Planning input gaps",
        summary_detailed="Lists missing optional sources only; no fabricated tasks.",
    )
    _write("planning_gaps_snapshot", snap)
    return snap


def build_live_work_index() -> dict[str, Any]:
    names = [
        "work_demand_snapshot",
        "time_constraints_snapshot",
        "daily_progress_snapshot",
        "communication_queue_snapshot",
        "planning_gaps_snapshot",
        "clickup_action_snapshot",
        "ingestion/repo_activity_snapshot",
        "ingestion/github_activity_snapshot",
        "ingestion/bills_snapshot",
        "timetable_snapshot",
    ]
    rows = []
    for n in names:
        p = live_work_dir() / (f"{n}.json" if "/" not in n else f"{n}.json")
        row = {"snapshot_type": n, "path": str(p), "exists": p.is_file()}
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                row["generated_at"] = d.get("generated_at")
                row["confidence"] = d.get("confidence")
                row["stale"] = d.get("stale")
            except Exception:
                row["error"] = "read_failed"
        rows.append(row)
    payload = {"generated_at": now_iso(), "snapshots": rows, "live_work_orchestration_version": 12}
    (live_work_dir() / "index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def build_all_live_work_snapshots() -> dict[str, Any]:
    """Build all Phase 9–17 snapshots in dependency order."""
    out: dict[str, Any] = {}
    from brain.live_work_orchestration.ingestion.bills import build_bills_snapshot
    from brain.live_work_orchestration.ingestion.github_activity import build_github_activity_snapshot
    from brain.live_work_orchestration.ingestion.repo_activity import build_repo_activity_snapshot

    out["repo_activity_snapshot"] = build_repo_activity_snapshot()
    out["github_activity_snapshot"] = build_github_activity_snapshot(
        repo_activity_snapshot=out["repo_activity_snapshot"]
    )
    out["bills_snapshot"] = build_bills_snapshot()
    out["work_demand_snapshot"] = build_work_demand_snapshot()
    out["time_constraints_snapshot"] = build_time_constraints_snapshot()
    out["daily_progress_snapshot"] = build_daily_progress_snapshot()
    out["communication_queue_snapshot"] = build_communication_queue_snapshot()
    out["planning_gaps_snapshot"] = build_planning_gaps_snapshot()
    out["clickup_action_snapshot"] = build_clickup_action_snapshot()
    out["timetable_snapshot"] = build_timetable_snapshot()
    out["index"] = build_live_work_index()
    return out
