"""
Prepared context builders.
"""
from __future__ import annotations

import os
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from brain import ops_registry
from brain.prepared_context.schema import PreparedSnapshot, now_iso
from brain.prepared_context.store import SNAPSHOT_NAMES, load_snapshot
from brain.worker_health import get_worker_health_snapshot, worker_health_snapshot_to_dict


def _repos_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ai_lab_root() -> Path:
    """ai-lab package root (parent of `brain/`)."""
    return Path(__file__).resolve().parents[2]


def _personal_ops_config_files() -> list[Path]:
    root = _ai_lab_root()
    return [
        root / "config" / "personal_ops.yaml",
        root / "config" / "personal_ops.example.yaml",
    ]


def _load_yaml_dict(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        raw = yaml.safe_load(text)
        return raw if isinstance(raw, dict) else {}
    except ImportError:
        return {}


def _heartbeat_snippet(path: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        return out
    out["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    try:
        hb = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(hb, dict):
            out["keys"] = sorted(hb.keys())[:30]
            for k in ("ts", "timestamp", "updated_at", "last_ok", "status"):
                if k in hb:
                    out[k] = hb.get(k)
    except Exception as exc:
        out["parse_error"] = str(exc)
    return out


def _event_start_str(ev: dict[str, Any]) -> str:
    st = ev.get("start")
    if isinstance(st, dict):
        return str(st.get("dateTime") or st.get("date") or "")
    return ""


def _slim_calendar_events(raw: list[dict[str, Any]], *, today_prefix: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split into today vs upcoming (rest), using UTC date prefix on start string."""
    today_ev: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for ev in raw:
        s = _event_start_str(ev)
        slim: dict[str, Any] = {
            "id": ev.get("id"),
            "summary": ev.get("summary"),
            "start": s,
            "status": ev.get("status"),
        }
        if s[:10] == today_prefix[:10]:
            today_ev.append(slim)
        else:
            upcoming.append(slim)
    return today_ev, upcoming


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
        "stale_repos_needing_attention": blocked[:8],
        "missing_sources": [],
    }
    if not changed:
        data["missing_sources"].append("no_recent_repo_changes")
    if not stale:
        data["missing_sources"].append("no_stale_repo_signals")
    # Optional enrichment from latest personal_ops snapshot (calendar and reminders).
    try:
        pos = load_snapshot("personal_ops_snapshot")
        pos_data = (pos or {}).get("data") if isinstance(pos, dict) else {}
        if isinstance(pos_data, dict):
            data["calendar_today_preview"] = list(pos_data.get("calendar_today") or [])[:5]
            data["calendar_upcoming_preview"] = list(pos_data.get("calendar_upcoming") or [])[:5]
            if data.get("calendar_today_preview") or data.get("calendar_upcoming_preview"):
                data["missing_sources"] = [m for m in data["missing_sources"] if m != "calendar_not_configured"]
            else:
                data["missing_sources"].append("calendar_not_configured")
        else:
            data["missing_sources"].append("no_personal_ops_snapshot")
    except Exception:
        data["missing_sources"].append("no_personal_ops_snapshot")
    evidence_items = [
        {
            "title": "Agenda from repo pulse",
            "source_path_or_tool": "prepared_context.repo_pulse",
            "observed_at": now_iso(),
            "summary": f"top_focus={top_focus[:3]} blocked={blocked[:3]}",
            "confidence": 0.75,
        }
    ]
    evidence_items.append(
        {
            "title": "Active projects and next actions",
            "source_path_or_tool": "prepared_context.repo_pulse.changed_repos",
            "observed_at": now_iso(),
            "summary": (
                f"active={len(data['active_projects'])} priorities={len(data['current_priorities'])} "
                f"next_actions={len(data['next_actions'])}"
            ),
            "confidence": 0.72 if data["active_projects"] else 0.5,
        }
    )
    evidence_items.append(
        {
            "title": "Blockers and stale repos",
            "source_path_or_tool": "prepared_context.repo_pulse.stale_repos",
            "observed_at": now_iso(),
            "summary": (
                f"blocked_items={len(data['blocked_items'])} "
                f"stale_repos_needing_attention={len(data['stale_repos_needing_attention'])}"
            ),
            "confidence": 0.7 if data["blocked_items"] else 0.55,
        }
    )
    if data.get("calendar_today_preview") or data.get("calendar_upcoming_preview"):
        evidence_items.append(
            {
                "title": "Calendar context (from personal ops)",
                "source_path_or_tool": "state/prepared_context/personal_ops_snapshot.json",
                "observed_at": now_iso(),
                "summary": (
                    f"today={len(data.get('calendar_today_preview') or [])} "
                    f"upcoming={len(data.get('calendar_upcoming_preview') or [])}"
                ),
                "confidence": 0.65,
            }
        )
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
    """
    Daily-planning snapshot: config-driven repo pulse, optional calendar window,
    Kylo heartbeat files, and cached project_agenda when present.
    """
    started = time.monotonic()
    errs: list[str] = []
    scripts_dir = _repos_root() / "ai-lab" / "scripts"
    script_names = [
        "personal_ops_calendar_snapshot.py",
        "personal_ops_daily_digest.py",
        "personal_ops_repo_pulse.py",
    ]
    available = [n for n in script_names if (scripts_dir / n).exists()]
    src: list[str] = [str(scripts_dir)]

    cfg_path: Path | None = None
    cfg: dict[str, Any] = {}
    for candidate in _personal_ops_config_files():
        if candidate.is_file():
            cfg_path = candidate
            try:
                cfg = _load_yaml_dict(candidate)
            except Exception as e:
                errs.append(f"personal_ops_config: {e}")
                cfg = {}
            break

    if cfg_path:
        src.insert(0, str(cfg_path))

    warn_days = float(cfg.get("stale_warning_days") or 7)
    data: dict[str, Any] = {
        "config_path": str(cfg_path) if cfg_path else None,
        "calendar_events": [],
        "calendar_today": [],
        "calendar_upcoming": [],
        "calendar_horizon_days": 7,
        "reminders": [],
        "daily_digest_available": (scripts_dir / "personal_ops_daily_digest.py").exists(),
        "repo_pulse": [],
        "stale_repo_labels": [],
        "kylo_heartbeats": [],
        "project_focus": {},
        "project_schedule": [],
        "incomplete_planned_items": [],
        "alerts_sent": [],
        "available_scripts": available,
    }
    evidence_items: list[dict[str, Any]] = []

    if cfg_path:
        evidence_items.append(
            {
                "title": "Personal ops config",
                "source_path_or_tool": str(cfg_path),
                "observed_at": now_iso(),
                "summary": f"loaded keys={sorted(cfg.keys())[:12]}",
                "confidence": 0.82,
            }
        )

    evidence_items.append(
        {
            "title": "Personal ops script availability",
            "source_path_or_tool": str(scripts_dir),
            "observed_at": now_iso(),
            "summary": f"available_scripts={available}",
            "confidence": 0.65 if available else 0.4,
        }
    )

    repos_cfg = cfg.get("repos") or []
    if isinstance(repos_cfg, list) and repos_cfg:
        try:
            from lib.repo_staleness import scan_repos

            pulses = scan_repos(repos_cfg)
            data["repo_pulse"] = [
                {
                    "label": p.label,
                    "path": p.path,
                    "days_idle": p.days_idle,
                    "last_commit_iso": p.last_commit_iso,
                    "error": p.error,
                }
                for p in pulses
            ]
            data["stale_repo_labels"] = [
                p.label for p in pulses if p.days_idle is not None and p.days_idle >= warn_days and not p.error
            ]
            evidence_items.append(
                {
                    "title": "Repo pulse (git idle)",
                    "source_path_or_tool": "lib.repo_staleness.scan_repos",
                    "observed_at": now_iso(),
                    "summary": f"repos={len(pulses)} stale={len(data['stale_repo_labels'])}",
                    "confidence": 0.78,
                }
            )
        except Exception as e:
            errs.append(f"repo_pulse: {e}")

    hb_cfg = cfg.get("kylo_heartbeats") or []
    if isinstance(hb_cfg, list) and hb_cfg:
        for item in hb_cfg:
            raw = item.get("path") if isinstance(item, dict) else str(item)
            if not raw:
                continue
            sn = _heartbeat_snippet(Path(str(raw)).expanduser())
            data["kylo_heartbeats"].append(sn)
        if data["kylo_heartbeats"]:
            evidence_items.append(
                {
                    "title": "Kylo / worker heartbeats",
                    "source_path_or_tool": "config.kylo_heartbeats",
                    "observed_at": now_iso(),
                    "summary": f"files={len(data['kylo_heartbeats'])}",
                    "confidence": 0.7,
                }
            )

    cal_block = cfg.get("calendar") if isinstance(cfg.get("calendar"), dict) else {}
    cal_id = (cal_block.get("calendar_id") or ("primary" if cal_block.get("primary") else None)) if cal_block else None
    horizon = int(data.get("calendar_horizon_days") or 7)
    # Avoid calling Google when only the checked-in example YAML is present (primary calendar).
    calendar_network_ok = bool(cal_id and cfg_path and cfg_path.name != "personal_ops.example.yaml")
    if calendar_network_ok:
        try:
            from lib.google_calendar_client import get_calendar_service, list_events, preflight_calendar_auth

            pre = preflight_calendar_auth()
            if not pre.get("ok"):
                errs.append("calendar: preflight not ok (credentials/token)")
            else:
                svc = get_calendar_service()
                now = datetime.now(timezone.utc)
                end = now + timedelta(days=horizon)
                tfmt = "%Y-%m-%dT%H:%M:%SZ"
                raw_ev = list_events(
                    svc,
                    str(cal_id),
                    time_min=now.strftime(tfmt),
                    time_max=end.strftime(tfmt),
                    max_results=120,
                )
                today_prefix = now.strftime("%Y-%m-%d")
                today_ev, upcoming = _slim_calendar_events(raw_ev, today_prefix=today_prefix)
                data["calendar_events"] = today_ev + upcoming[:50]
                data["calendar_today"] = today_ev[:20]
                data["calendar_upcoming"] = upcoming[:30]
                evidence_items.append(
                    {
                        "title": "Google Calendar window",
                        "source_path_or_tool": "lib.google_calendar_client.list_events",
                        "observed_at": now_iso(),
                        "summary": f"calendar_id={cal_id} events={len(data['calendar_events'])}",
                        "confidence": 0.85 if data["calendar_events"] else 0.55,
                    }
                )
        except Exception as e:
            errs.append(f"calendar: {e}")

    pa = load_snapshot("project_agenda")
    missing_sources: list[str] = []
    if not cal_id or not calendar_network_ok:
        missing_sources.append("calendar_not_configured")
    if not isinstance(pa, dict) or not isinstance(pa.get("data"), dict):
        missing_sources.append("no_project_agenda_snapshot")
    if not data.get("alerts_sent"):
        missing_sources.append("no_recent_alerts")
    data["missing_sources"] = missing_sources

    if isinstance(pa, dict) and isinstance(pa.get("data"), dict):
        pad = pa["data"]
        data["project_focus"] = {
            "today_focus": pad.get("today_focus") or [],
            "current_priorities": pad.get("current_priorities") or [],
            "blocked_items": pad.get("blocked_items") or [],
            "overdue_tasks": pad.get("overdue_tasks") or [],
            "next_actions": pad.get("next_actions") or [],
        }
        data["incomplete_planned_items"] = list(pad.get("blocked_items") or [])[:8]
        data["project_schedule"] = list(pad.get("next_actions") or [])[:8]
        # Lightweight alerts summary for planning prompts and missing_sources diagnostics.
        agenda_blocked = list(pad.get("blocked_items") or [])[:5]
        stale_repos = list(data.get("stale_repo_labels") or [])[:5]
        alerts: list[dict[str, Any]] = []
        if agenda_blocked:
            alerts.append(
                {
                    "kind": "blocked_items",
                    "count": len(agenda_blocked),
                    "items": agenda_blocked,
                }
            )
        if stale_repos:
            alerts.append(
                {
                    "kind": "stale_repos",
                    "count": len(stale_repos),
                    "items": stale_repos,
                }
            )
        data["alerts_sent"] = alerts
        if alerts and "no_recent_alerts" in missing_sources:
            missing_sources.remove("no_recent_alerts")
        evidence_items.append(
            {
                "title": "Project agenda (cached)",
                "source_path_or_tool": "state/prepared_context/project_agenda.json",
                "observed_at": pa.get("generated_at") or now_iso(),
                "summary": "Merged last-built project_agenda for planning context.",
                "confidence": 0.72,
            }
        )
        evidence_items.append(
            {
                "title": "Planning detail depth",
                "source_path_or_tool": "personal_ops_snapshot.project_focus",
                "observed_at": now_iso(),
                "summary": (
                    f"today_focus={len(data['project_focus'].get('today_focus') or [])} "
                    f"next_actions={len(data['project_schedule'])} "
                    f"blocked={len(data['incomplete_planned_items'])}"
                ),
                "confidence": 0.74 if data["project_schedule"] else 0.58,
            }
        )
    if data.get("stale_repo_labels"):
        evidence_items.append(
            {
                "title": "Stale repos needing attention",
                "source_path_or_tool": "lib.repo_staleness.scan_repos",
                "observed_at": now_iso(),
                "summary": f"stale_repo_labels={data['stale_repo_labels'][:8]}",
                "confidence": 0.7,
            }
        )
    if data.get("calendar_today") or data.get("calendar_upcoming"):
        evidence_items.append(
            {
                "title": "Calendar planning cues",
                "source_path_or_tool": "lib.google_calendar_client.list_events",
                "observed_at": now_iso(),
                "summary": (
                    f"today={len(data.get('calendar_today') or [])} "
                    f"upcoming={len(data.get('calendar_upcoming') or [])}"
                ),
                "confidence": 0.74,
            }
        )
    if data.get("daily_digest_available"):
        evidence_items.append(
            {
                "title": "Daily digest script available",
                "source_path_or_tool": str(scripts_dir / "personal_ops_daily_digest.py"),
                "observed_at": now_iso(),
                "summary": "daily digest tool available for operator check-ins",
                "confidence": 0.62,
            }
        )

    has_planning_signal = bool(
        data.get("repo_pulse") or data.get("calendar_events") or data.get("project_focus") or data.get("kylo_heartbeats")
    )
    freshness = 86400
    summary_short = (
        "Personal planning snapshot: repo activity + optional calendar + agenda cues."
        if has_planning_signal
        else "Personal ops snapshot: limited data (see config, credentials, and project_agenda freshness)."
    )
    summary_detailed = (
        "Combines personal_ops.yaml (or example), git repo idle scan, optional Google Calendar events, "
        "Kylo heartbeat paths, and on-disk project_agenda when available. Use for daily planning questions."
    )
    base_conf = 0.72 if has_planning_signal else 0.42
    if not cfg_path:
        base_conf = min(base_conf, 0.38)

    return PreparedSnapshot(
        snapshot_type="personal_ops_snapshot",
        generated_at=now_iso(),
        freshness_seconds=freshness,
        source_files_or_tools=src,
        confidence=_confidence_from_evidence(evidence_items, base=base_conf, errors=errs),
        stale=_is_stale(started, freshness),
        errors=errs,
        data=data,
        summary_short=summary_short,
        summary_detailed=summary_detailed,
        suggested_questions=[
            "what is on my calendar today?",
            "what should I focus on today?",
            "which repos are stale?",
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
                sv = payload.get("schema_verification") if isinstance(payload.get("schema_verification"), dict) else {}
                drift = sv.get("drift") if isinstance(sv.get("drift"), dict) else {}
                crit = drift.get("critical_missing_paths") if isinstance(drift.get("critical_missing_paths"), list) else []
                drift_active = bool(
                    drift.get("missing_paths") or drift.get("added_paths") or drift.get("critical_missing_paths")
                )
                merged_warnings: list[Any] = []
                for key in (
                    "warnings",
                    "sanity_warnings",
                    "schema_drift_warnings",
                    "parser_warnings",
                    "target_alignment_warnings",
                ):
                    chunk = payload.get(key)
                    if isinstance(chunk, list):
                        merged_warnings.extend(chunk)
                seen_w: set[str] = set()
                deduped_warnings: list[Any] = []
                for w in merged_warnings:
                    sw = str(w)
                    if sw not in seen_w:
                        seen_w.add(sw)
                        deduped_warnings.append(w)
                metric_status = {
                    "ok": bool(payload.get("ok")),
                    "confidence": payload.get("confidence"),
                    "confidence_score": payload.get("confidence_score"),
                    "confidence_label": payload.get("confidence"),
                    "field_confidence_counts": payload.get("field_confidence_counts") or {},
                    "schema_drift_summary": {
                        "baseline_exists": bool(sv.get("baseline_exists")),
                        "drift": drift_active,
                        "critical_missing_paths_count": len(crit),
                    },
                    "warnings": deduped_warnings,
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

