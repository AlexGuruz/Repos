"""
Prepared context builders.
"""
from __future__ import annotations

import os
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from brain import ops_registry
from brain.prepared_context.schema import PreparedSnapshot, now_iso
from brain.prepared_context.store import SNAPSHOT_NAMES
from brain.worker_health import get_worker_health_snapshot, worker_health_snapshot_to_dict


def _repos_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _is_stale(generated_monotonic: float, freshness_seconds: int) -> bool:
    return (time.monotonic() - generated_monotonic) > freshness_seconds


def _git_recent_commits(repo: Path, limit: int = 3) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", f"-{limit}", "--pretty=%h %s"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if out.returncode != 0:
            return []
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _count_todo_fixme(repo: Path, max_files: int = 80) -> int:
    count = 0
    scanned = 0
    for ext in ("*.py", "*.md", "*.ts", "*.tsx", "*.js", "*.jsx"):
        for p in repo.rglob(ext):
            if scanned >= max_files:
                return count
            scanned += 1
            try:
                txt = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            count += txt.count("TODO")
            count += txt.count("FIXME")
    return count


def _confidence_from_evidence(evidence_items: list[dict[str, Any]], base: float, errors: list[str]) -> float:
    if not evidence_items:
        return max(0.25, base - 0.45)
    uniq_sources = len({str(e.get("source_path_or_tool") or "") for e in evidence_items})
    conf = base
    if len(evidence_items) <= 1 or uniq_sources <= 1:
        conf -= 0.2
    if errors:
        conf -= min(0.25, 0.08 * len(errors))
    return max(0.25, min(0.95, round(conf, 3)))


def build_system_snapshot() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    src = ["ops_registry.get_ops_summary_text_cached", "brain/session_store", "brain/worker_health"]
    data: dict[str, Any] = {}
    evidence_items: list[dict[str, Any]] = []
    try:
        summary = ops_registry.get_ops_summary_text_cached()
        data["ops_summary"] = summary
        systems = ops_registry.load_systems().get("systems", {})
        workers = ops_registry.load_workers().get("workers", {})
        automations = ops_registry.load_automations().get("automations", {})
        data["active_systems"] = list(systems.keys())[:20] if isinstance(systems, dict) else []
        data["known_services"] = list(automations.keys())[:30] if isinstance(automations, dict) else []
        data["active_repos"] = [
            v.get("repo") for v in systems.values() if isinstance(v, dict) and v.get("repo")
        ][:30] if isinstance(systems, dict) else []
        data["command_center_status"] = {
            "configured": True,
            "backend_router": "command-center/backend/main.py",
        }
        data["last_successful_checks"] = {"ops_registry_loaded_at": now_iso()}
        evidence_items.append(
            {
                "title": "Ops registry summary",
                "source_path_or_tool": "ops_registry.get_ops_summary_text_cached",
                "observed_at": now_iso(),
                "summary": "Loaded systems/workers/automations registries.",
                "confidence": 0.9,
            }
        )
    except Exception as e:
        errs.append(f"ops_summary: {e}")
        data["ops_summary"] = ""
    try:
        worker = worker_health_snapshot_to_dict(get_worker_health_snapshot("worker-rig-01", timeout_budget_ms=2000, interactive=True))
        data["worker_health"] = worker
        data["worker_summary"] = {
            "worker_status": worker.get("worker_status"),
            "services": [s.get("name") for s in worker.get("services", []) if isinstance(s, dict)],
        }
        evidence_items.append(
            {
                "title": "Worker health snapshot",
                "source_path_or_tool": "brain.worker_health.get_worker_health_snapshot",
                "observed_at": worker.get("checked_at") or now_iso(),
                "summary": f"worker_status={worker.get('worker_status')}",
                "confidence": 0.9 if worker.get("worker_status") else 0.6,
            }
        )
    except Exception as e:
        errs.append(f"worker_health: {e}")
        data["worker_health"] = {}
    # Recent fallback/exception hints from trace tail.
    try:
        tf = _repos_root() / "ai-lab" / "state" / "ai_response_traces.jsonl"
        recent_errors = []
        if tf.exists():
            lines = tf.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
            for ln in reversed(lines):
                try:
                    row = json.loads(ln)
                except Exception:
                    continue
                if row.get("fallback_reason"):
                    recent_errors.append({"fallback_reason": row.get("fallback_reason"), "message": row.get("user_message", "")[:120]})
                if len(recent_errors) >= 8:
                    break
        data["recent_errors"] = recent_errors
    except Exception:
        data["recent_errors"] = []
    confidence = _confidence_from_evidence(evidence_items, base=0.86, errors=errs)
    freshness = 900
    return PreparedSnapshot(
        snapshot_type="system_snapshot",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=src,
        confidence=confidence,
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short="Systems snapshot with ops + worker health.",
        summary_detailed="Prepared snapshot for system status questions (active systems, running/broken services, worker/tunnel state).",
        suggested_questions=[
            "what systems are active?",
            "what is running?",
            "what is broken?",
            "check system status",
        ],
        evidence_items=evidence_items,
    )


def build_repo_pulse() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    root = _repos_root()
    repos: list[dict[str, Any]] = []
    src = [str(root)]
    try:
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if (child / ".git").exists():
                readme = child / "README.md"
                commits = _git_recent_commits(child, limit=3)
                todo_fixme = _count_todo_fixme(child, max_files=50)
                mtime = child.stat().st_mtime
                stale_repo = (time.time() - mtime) > 30 * 86400
                repos.append(
                    {
                        "repo": child.name,
                        "path": str(child),
                        "stale": stale_repo,
                        "readme_present": readme.exists(),
                        "readme_fresh": readme.exists() and ((time.time() - readme.stat().st_mtime) < 45 * 86400),
                        "todo_fixme_count": todo_fixme,
                        "recent_commits": commits,
                        "last_modified_epoch": mtime,
                        "role": "unknown",
                    }
                )
            if len(repos) >= 40:
                break
    except Exception as e:
        errs.append(f"repo_scan: {e}")
    changed = sorted(repos, key=lambda r: r.get("last_modified_epoch", 0), reverse=True)[:10]
    stale = [r for r in repos if r.get("stale")]
    docs_need = [r["repo"] for r in repos if not r.get("readme_fresh")]
    evidence_items: list[dict[str, Any]] = []
    for r in changed[:6]:
        evidence_items.append(
            {
                "title": f"Repo pulse: {r.get('repo')}",
                "source_path_or_tool": r.get("path"),
                "observed_at": now_iso(),
                "summary": f"readme_fresh={r.get('readme_fresh')} stale={r.get('stale')} todo_fixme={r.get('todo_fixme_count')}",
                "confidence": 0.8,
            }
        )
    data = {
        "changed_repos": changed,
        "stale_repos": stale[:10],
        "docs_needing_updates": docs_need[:12],
        "readme_freshness": {r.get("repo"): r.get("readme_fresh") for r in repos[:30]},
        "repos": repos,
    }
    freshness = 3600
    confidence = _confidence_from_evidence(evidence_items, base=0.82 if repos else 0.5, errors=errs)
    return PreparedSnapshot(
        snapshot_type="repo_pulse",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=src + ["git log", "README.md scan", "TODO/FIXME scan"],
        confidence=confidence,
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short=f"Repo pulse built for {len(repos)} repos.",
        summary_detailed="Tracks changed repos, stale repos, docs freshness, TODO/FIXME density, and recent commits where available.",
        suggested_questions=[
            "what changed recently?",
            "what repo needs cleanup?",
            "what docs are stale?",
            "summarize repo status",
        ],
        evidence_items=evidence_items,
    )


def build_project_agenda() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    rp = build_repo_pulse().data
    changed = rp.get("changed_repos") or []
    stale = rp.get("stale_repos") or []
    top_focus = [r.get("repo") for r in changed[:5] if isinstance(r, dict)]
    blocked = [r.get("repo") for r in stale[:5] if isinstance(r, dict)]
    data = {
        "active_projects": top_focus,
        "current_priorities": top_focus[:3],
        "next_actions": [f"Review {x}" for x in top_focus[:3]],
        "blocked_items": [f"{x}: stale/no recent updates" for x in blocked[:3]],
        "overdue_tasks": [f"{x}: refresh README/docs" for x in blocked[:3]],
        "today_focus": top_focus[:3],
        "tomorrow_focus": top_focus[3:6],
        "project_to_repo_map": {x: x for x in top_focus},
    }
    evidence_items = [
        {
            "title": "Agenda from repo pulse",
            "source_path_or_tool": "prepared_context.repo_pulse",
            "observed_at": now_iso(),
            "summary": f"top_focus={top_focus[:3]} blocked={blocked[:3]}",
            "confidence": 0.75,
        }
    ]
    freshness = 86400
    return PreparedSnapshot(
        snapshot_type="project_agenda",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=["repo_pulse", "ops_registry"],
        confidence=_confidence_from_evidence(evidence_items, base=0.75 if top_focus else 0.45, errors=errs),
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short="Project agenda prepared from repo pulse and activity.",
        summary_detailed="Daily planning context: priorities, next actions, blocked/overdue signals, and project-to-repo mapping.",
        suggested_questions=[
            "what should I work on today?",
            "what is next?",
            "what am I blocked on?",
            "make me a daily plan",
        ],
        evidence_items=evidence_items,
    )


def build_personal_ops_snapshot() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    root = _repos_root() / "ai-lab" / "scripts"
    src = [str(root)]
    script_names = [
        "personal_ops_calendar_snapshot.py",
        "personal_ops_daily_digest.py",
        "personal_ops_repo_pulse.py",
    ]
    available = [n for n in script_names if (root / n).exists()]
    data = {
        "calendar_events": [],
        "reminders": [],
        "daily_digest_available": (root / "personal_ops_daily_digest.py").exists(),
        "project_schedule": [],
        "incomplete_planned_items": [],
        "alerts_sent": [],
        "available_scripts": available,
    }
    evidence_items = [
        {
            "title": "Personal ops script availability",
            "source_path_or_tool": str(root),
            "observed_at": now_iso(),
            "summary": f"available_scripts={available}",
            "confidence": 0.65 if available else 0.4,
        }
    ]
    freshness = 86400
    return PreparedSnapshot(
        snapshot_type="personal_ops_snapshot",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=src,
        confidence=_confidence_from_evidence(evidence_items, base=0.65 if available else 0.4, errors=errs),
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short="Personal ops snapshot prepared from available personal_ops scripts.",
        summary_detailed="Calendar/digest/planning readiness snapshot with available personal operations tooling and placeholders for integrations.",
        suggested_questions=[
            "what is on my calendar today?",
            "what reminders are pending?",
            "show my daily assistant snapshot",
        ],
        evidence_items=evidence_items,
    )


def build_growflow_snapshot() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    root = _repos_root() / "Growflow"
    src = [str(root / "company_bi" / "METRICS.md"), str(root / "exports"), str(root / "state" / "validation_reports")]
    metrics = root / "company_bi" / "METRICS.md"
    exports = root / "exports"
    data: dict[str, Any] = {
        "latest_sales_summary": None,
        "inventory_par_health": None,
        "transfer_receipt_status": None,
        "dashboard_export_status": None,
        "recent_automation_failures": [],
        "data_freshness_timestamps": {},
        "latest_successful_exports": [],
        "par_inventory_pipeline_status": "unknown",
        "known_blockers": [],
        "validation_status_by_metric": {},
        "validation_failures": [],
        "schema_drift_warnings": [],
        "latest_trusted_output_by_metric": {},
    }
    evidence_items: list[dict[str, Any]] = []
    try:
        if metrics.exists():
            text = metrics.read_text(encoding="utf-8", errors="replace")
            data["latest_sales_summary"] = text[:1200]
            data["data_freshness_timestamps"]["metrics_mtime"] = metrics.stat().st_mtime
            evidence_items.append(
                {
                    "title": "Growflow metrics",
                    "source_path_or_tool": str(metrics),
                    "observed_at": now_iso(),
                    "summary": "Loaded METRICS.md sales/business summary.",
                    "confidence": 0.85,
                }
            )
    except Exception as e:
        errs.append(f"metrics_read: {e}")
        data["known_blockers"].append(f"metrics_read: {e}")
    try:
        if exports.exists():
            files = sorted([p for p in exports.iterdir() if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
            if files:
                data["dashboard_export_status"] = {"latest_file": files[0].name, "mtime": files[0].stat().st_mtime}
                data["latest_successful_exports"] = [f.name for f in files[:8]]
                data["transfer_receipt_status"] = "available" if any("transfer" in f.name.lower() for f in files[:20]) else "unknown"
                evidence_items.append(
                    {
                        "title": "Growflow exports",
                        "source_path_or_tool": str(exports),
                        "observed_at": now_iso(),
                        "summary": f"latest_export={files[0].name}",
                        "confidence": 0.8,
                    }
                )
    except Exception as e:
        errs.append(f"exports_scan: {e}")
        data["known_blockers"].append(f"exports_scan: {e}")
    try:
        vr = root / "state" / "validation_reports"
        to = root / "state" / "trusted_outputs"
        rr = root / "state" / "raw_responses"
        if vr.exists():
            for metric_dir in sorted([p for p in vr.iterdir() if p.is_dir()]):
                reports = sorted([p for p in metric_dir.glob("*.json")], key=lambda p: p.stat().st_mtime, reverse=True)
                if not reports:
                    continue
                latest = reports[0]
                payload = json.loads(latest.read_text(encoding="utf-8", errors="replace"))
                metric_id = str(payload.get("metric_id") or metric_dir.name)
                metric_status = {
                    "ok": bool(payload.get("ok")),
                    "confidence": payload.get("confidence"),
                    "warnings": payload.get("warnings") or payload.get("sanity_warnings") or [],
                    "errors": payload.get("errors") or payload.get("hard_failures") or [],
                    "normalized_row_count": payload.get("normalized_row_count"),
                    "generated_at": payload.get("generated_at"),
                    "report_path": str(latest),
                    "last_raw_response_timestamp": None,
                    "last_trusted_output_timestamp": None,
                }
                raw_metric = rr / metric_id
                if raw_metric.exists():
                    raw_files = sorted(raw_metric.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if raw_files:
                        metric_status["last_raw_response_timestamp"] = datetime.fromtimestamp(raw_files[0].stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
                trusted_metric = to / metric_id
                if trusted_metric.exists():
                    trust_files = sorted(trusted_metric.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if trust_files:
                        ts = datetime.fromtimestamp(trust_files[0].stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
                        metric_status["last_trusted_output_timestamp"] = ts
                        data["latest_trusted_output_by_metric"][metric_id] = str(trust_files[0])
                data["validation_status_by_metric"][metric_id] = metric_status
                if not metric_status["ok"]:
                    data["validation_failures"].append({"metric_id": metric_id, "report_path": str(latest)})
                for warn in metric_status["warnings"] or []:
                    w = str(warn)
                    if "schema" in w.lower() or "root" in w.lower() or "field" in w.lower():
                        data["schema_drift_warnings"].append({"metric_id": metric_id, "warning": w})
    except Exception as e:
        errs.append(f"validation_scan: {e}")
        data["known_blockers"].append(f"validation_scan: {e}")
    data["par_inventory_pipeline_status"] = "likely_available" if (root / "scripts").exists() else "unknown"
    if not data.get("latest_sales_summary"):
        data["known_blockers"].append("latest_sales_summary_missing")
    if data.get("validation_failures"):
        data["known_blockers"].append("latest_validation_failed")
    freshness = 3600
    return PreparedSnapshot(
        snapshot_type="growflow_snapshot",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=src,
        confidence=_confidence_from_evidence(evidence_items, base=0.8 if data.get("latest_sales_summary") else 0.45, errors=errs),
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short="Growflow/business snapshot from local metrics and export artifacts.",
        summary_detailed="Business automation health snapshot with sales summary availability, export freshness, and data timestamp signals.",
        suggested_questions=[
            "what is Growflow status?",
            "is business data fresh?",
            "what is the dashboard export status?",
        ],
        evidence_items=evidence_items,
    )


def build_worker_snapshot() -> PreparedSnapshot:
    started = time.monotonic()
    errs: list[str] = []
    try:
        snap = get_worker_health_snapshot("worker-rig-01", timeout_budget_ms=2000, interactive=True)
        payload = worker_health_snapshot_to_dict(snap)
    except Exception as e:
        errs.append(str(e))
        payload = {"worker_status": "offline_or_unreachable"}
    evidence_items = [
        {
            "title": "Worker health",
            "source_path_or_tool": "brain.worker_health.get_worker_health_snapshot",
            "observed_at": payload.get("checked_at") if isinstance(payload, dict) else now_iso(),
            "summary": f"worker_status={payload.get('worker_status') if isinstance(payload, dict) else 'unknown'}",
            "confidence": 0.9 if isinstance(payload, dict) and payload.get("worker_status") else 0.5,
        }
    ]
    freshness = 900
    return PreparedSnapshot(
        snapshot_type="worker_snapshot",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=["brain.worker_health", "brain.worker_tunnel"],
        confidence=_confidence_from_evidence(evidence_items, base=0.9 if not errs else 0.5, errors=errs),
        stale=_is_stale(started, freshness),
        errors=errs,
        data=payload,
        summary_short="Worker snapshot with health and tunnel state.",
        summary_detailed="Worker online/offline, service availability (assistant/n8n/ollama), tunnel state, and last-known status.",
        suggested_questions=[
            "check worker health",
            "is ollama available on worker?",
            "should I offload to worker?",
        ],
        evidence_items=evidence_items,
    )


def build_snapshot(snapshot_type: str) -> PreparedSnapshot:
    mapping = {
        "system_snapshot": build_system_snapshot,
        "repo_pulse": build_repo_pulse,
        "project_agenda": build_project_agenda,
        "personal_ops_snapshot": build_personal_ops_snapshot,
        "growflow_snapshot": build_growflow_snapshot,
        "worker_snapshot": build_worker_snapshot,
    }
    if snapshot_type not in mapping:
        raise ValueError(f"Unknown snapshot type: {snapshot_type}")
    return mapping[snapshot_type]()


def build_all_snapshots() -> list[PreparedSnapshot]:
    return [build_snapshot(name) for name in SNAPSHOT_NAMES]

