"""
Phase 11 ingestion lane: local repo activity (read-only).

This module inspects local git metadata only (status/log/branch), builds progress signals,
and writes a dedicated ingestion snapshot used by daily progress synthesis.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """
    Minimal YAML parser for config/live_work_ingestion*.yaml.
    Supports simple two-level mappings and top-level lists.
    """
    if not path.is_file():
        return {}
    out: dict[str, Any] = {}
    section: str | None = None
    key_for_list: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1].strip()
            out[section] = {}
            key_for_list = None
            continue
        if section is None:
            continue
        s = line.strip()
        if s.startswith("- "):
            if key_for_list:
                out[section].setdefault(key_for_list, [])
                out[section][key_for_list].append(s[2:].strip().strip('"').strip("'"))
            continue
        if ":" not in s:
            continue
        k, v = s.split(":", 1)
        key = k.strip()
        value = v.strip()
        if value == "":
            key_for_list = key
            out[section][key] = []
            continue
        key_for_list = None
        low = value.lower()
        if low == "true":
            out[section][key] = True
        elif low == "false":
            out[section][key] = False
        elif low == "null":
            out[section][key] = None
        else:
            raw_v = value.strip('"').strip("'")
            if raw_v.isdigit():
                out[section][key] = int(raw_v)
            else:
                out[section][key] = raw_v
    return out


def _default_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    return {
        "repo_activity": {
            "enabled": True,
            "repo_roots": [str(root)],
            "scan_depth": 2,
            "include_file_samples": True,
            "max_file_samples": 20,
            "include_file_activity": True,
            "max_file_timestamp_samples": 25,
            "include_commit_subjects": True,
            "max_commit_subjects": 20,
            "include_commit_timestamps": True,
            "max_commit_timestamps": 20,
            "since_hours": 24,
        }
    }


def load_repo_activity_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    c = root / "config" / "live_work_ingestion.yaml"
    if not c.is_file():
        c = root / "config" / "live_work_ingestion.example.yaml"
    merged = _default_config()
    loaded = _parse_simple_yaml(c)
    lane = loaded.get("repo_activity") if isinstance(loaded, dict) else None
    if isinstance(lane, dict):
        merged["repo_activity"].update(lane)
    return merged


def _run_git(repo_path: Path, args: list[str]) -> tuple[bool, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return p.returncode == 0, (p.stdout or p.stderr or "").strip()
    except Exception as exc:
        return False, str(exc)


def discover_local_repos(repo_roots: list[str], scan_depth: int) -> list[Path]:
    """
    Discover git repositories by .git folder without broad filesystem scanning.
    """
    found: list[Path] = []
    for root in repo_roots:
        try:
            root_p = Path(root)
            if not root_p.exists() or not root_p.is_dir():
                continue
            # Root itself is a repo.
            if (root_p / ".git").exists():
                found.append(root_p)
            # Bounded breadth-first walk.
            queue: list[tuple[Path, int]] = [(root_p, 0)]
            while queue:
                cur, depth = queue.pop(0)
                if depth >= scan_depth:
                    continue
                try:
                    children = [x for x in cur.iterdir() if x.is_dir()]
                except Exception:
                    continue
                for child in children:
                    if child.name.startswith("."):
                        continue
                    if (child / ".git").exists():
                        found.append(child)
                        continue
                    queue.append((child, depth + 1))
        except Exception:
            continue
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in found:
        s = str(p.resolve())
        if s in seen:
            continue
        seen.add(s)
        uniq.append(p)
    return uniq


def _normalize_feature_name(raw: str, fallback: str) -> str:
    name = (raw or "").strip().strip("/")
    if not name:
        return fallback
    low = name.lower()
    for prefix in ("wip/", "tmp/", "test/", "fix/"):
        if low.startswith(prefix):
            stripped = name[len(prefix) :].strip("/")
            return stripped or fallback
    return name


def _infer_feature(repo_path: Path, branch: str) -> tuple[str, str, str]:
    b = (branch or "").strip()
    feature_name = _normalize_feature_name(b if b and b != "HEAD" else repo_path.name, repo_path.name)
    feature_area = "core"
    t = feature_name.lower()
    if any(k in t for k in ("docs", "readme", "wiki")):
        feature_area = "docs"
    elif any(k in t for k in ("test", "spec", "qa")):
        feature_area = "testing"
    elif any(k in t for k in ("infra", "ops", "deploy")):
        feature_area = "ops"
    stage = "unknown"
    if any(k in t for k in ("feat/", "feature/", "dev", "wip")):
        stage = "dev"
    elif any(k in t for k in ("test", "qa")):
        stage = "testing"
    elif any(k in t for k in ("review", "pr-", "ready")):
        stage = "review"
    return feature_name, feature_area, stage


def _classify_activity(
    changed: list[str], commit_count: int, last_commit_time: str | None
) -> tuple[bool, bool, bool, str, str]:
    docs = False
    tests = False
    for f in changed:
        fp = Path(f)
        parts = [x.lower() for x in fp.parts]
        if "docs" in parts or fp.suffix.lower() in (".md", ".rst", ".txt"):
            docs = True
        if "tests" in parts or "test" in fp.name.lower():
            tests = True
    code = any(
        Path(f).suffix.lower() in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt", ".cs")
        for f in changed
    )
    parts = [("code", code), ("docs", docs), ("tests", tests)]
    active = [name for name, on in parts if on]
    activity_type = active[0] if len(active) == 1 else ("mixed" if active else "docs")
    file_weight = 1.0
    if code:
        file_weight += 0.8
    if tests:
        file_weight += 0.5
    if docs and not code:
        file_weight -= 0.25
    recency_bonus = 0.0
    if last_commit_time:
        try:
            dt = datetime.fromisoformat(last_commit_time.replace("Z", "+00:00"))
            age_h = max(0.0, (_utc_now() - dt).total_seconds() / 3600.0)
            if age_h <= 2:
                recency_bonus = 2.0
            elif age_h <= 8:
                recency_bonus = 1.0
        except Exception:
            recency_bonus = 0.0
    score = (len(changed) * file_weight) + (max(commit_count, 0) * 1.8) + recency_bonus
    if score >= 20:
        intensity = "high"
    elif score >= 6:
        intensity = "medium"
    else:
        intensity = "low"
    return docs, tests, code, activity_type, intensity


def _lane_defaults(lane: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(_default_config()["repo_activity"])
    if isinstance(lane, dict):
        merged.update(lane)
    return merged


def _safe_repo_path(repo: Path, rel: str) -> Path | None:
    if not rel or rel.startswith("/"):
        return None
    cand = (repo / rel).resolve()
    try:
        cand.relative_to(repo.resolve())
    except ValueError:
        return None
    return cand


def _collect_file_mtimes(
    repo: Path, changed_files: list[str], max_n: int
) -> tuple[list[dict[str, Any]], datetime | None, datetime | None, int]:
    """Stat mtimes for changed/untracked paths only (no content reads)."""
    sample: list[dict[str, Any]] = []
    times: list[datetime] = []
    for rel in changed_files[:max_n]:
        fp = _safe_repo_path(repo, rel)
        if fp is None or not fp.is_file():
            continue
        try:
            st = os.stat(fp)
            m = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        except OSError:
            continue
        times.append(m)
        sample.append({"path": rel, "mtime_iso": m.replace(microsecond=0).isoformat().replace("+00:00", "Z")})
    if not times:
        return [], None, None, 0
    return sample, min(times), max(times), len(times)


def _fmt_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _git_hygiene_summary_text(
    *,
    clean_ish: bool,
    uncommitted: int,
    ahead: int,
    commit_needed: bool,
    push_needed: bool,
) -> str:
    parts: list[str] = []
    if push_needed:
        parts.append("Branch ahead of remote; push recommended")
    if commit_needed:
        parts.append("Active local changes not committed")
    if clean_ish and not push_needed:
        parts.append("Working tree clean")
    if not parts:
        parts.append("No special hygiene flags")
    return " | ".join(parts)


def _merge_activity_bounds(
    f_start: datetime | None,
    f_end: datetime | None,
    c_start: datetime | None,
    c_end: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    starts = [x for x in (f_start, c_start) if x is not None]
    ends = [x for x in (f_end, c_end) if x is not None]
    if not starts or not ends:
        return None, None
    st, en = min(starts), max(ends)
    if en < st:
        return None, None
    return st, en


def _git_has_remote(repo: Path) -> bool:
    ok, out = _run_git(repo, ["remote", "-v"])
    return ok and bool(out.strip())


def _git_upstream_ahead_behind(repo: Path) -> tuple[int, int]:
    ok, _ = _run_git(repo, ["rev-parse", "--verify", "@{upstream}"])
    if not ok:
        return 0, 0
    ok2, line = _run_git(repo, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"])
    if not ok2 or not line:
        return 0, 0
    parts = line.replace("\t", " ").split()
    if len(parts) < 2:
        return 0, 0
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 0, 0


def collect_repo_activity(
    repo_path: str | Path,
    since_hours: int | None = None,
    lane: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _lane_defaults(lane)
    p = Path(repo_path)
    observed = now_iso()
    base: dict[str, Any] = {
        "repo_name": p.name,
        "repo_path": str(p),
        "current_branch": "",
        "git_status_summary": "",
        "uncommitted_changes_count": 0,
        "changed_files_count": 0,
        "changed_files_sample": [],
        "recent_commits_count": 0,
        "recent_commit_subjects": [],
        "first_commit_time": None,
        "last_commit_time": None,
        "commit_timestamps": [],
        "file_activity_window_start": None,
        "file_activity_window_end": None,
        "modified_file_timestamps_sample": [],
        "modified_files_count": 0,
        "activity_window_start": None,
        "activity_window_end": None,
        "uncommitted_work_age_hours": None,
        "branch_ahead": 0,
        "branch_behind": 0,
        "has_remote": False,
        "commit_needed": False,
        "push_needed": False,
        "git_hygiene_summary": "",
        "docs_changed": False,
        "tests_changed": False,
        "code_changed": False,
        "likely_feature_name": p.name,
        "linked_pr_guess": None,
        "feature_area": "core",
        "rollout_stage": "unknown",
        "activity_type": "docs",
        "activity_intensity": "low",
        "observed_at": observed,
        "confidence": 0.4,
        "errors": [],
    }
    if not p.exists() or not p.is_dir():
        base["errors"].append("repo_path_not_found")
        return base
    if not (p / ".git").exists():
        base["errors"].append("not_a_git_repo")
        return base

    ok_branch, branch_out = _run_git(p, ["rev-parse", "--abbrev-ref", "HEAD"])
    if ok_branch:
        base["current_branch"] = branch_out.strip()
    else:
        base["errors"].append(f"branch:{branch_out}")

    ok_status, status_out = _run_git(p, ["status", "--short"])
    changed_files: list[str] = []
    if ok_status:
        lines = [x for x in status_out.splitlines() if x.strip()]
        for line in lines:
            right = line[3:].strip() if len(line) > 3 else line.strip()
            if " -> " in right:
                right = right.split(" -> ")[-1].strip()
            changed_files.append(right)
        base["git_status_summary"] = f"{len(lines)} changed entries"
        base["uncommitted_changes_count"] = len(lines)
        base["changed_files_count"] = len(changed_files)
        base["changed_files_sample"] = changed_files[: int(cfg.get("max_file_samples") or 20)]
    else:
        base["errors"].append(f"status:{status_out}")

    include_file_activity = bool(cfg.get("include_file_activity", True))
    max_file_ts = int(cfg.get("max_file_timestamp_samples") or 25)
    if include_file_activity and changed_files:
        sample, f0, f1, mcount = _collect_file_mtimes(p, changed_files, max_file_ts)
        base["modified_file_timestamps_sample"] = sample
        base["modified_files_count"] = mcount
        if f0 is not None and f1 is not None:
            base["file_activity_window_start"] = _fmt_z(f0)
            base["file_activity_window_end"] = _fmt_z(f1)

    max_ct = max(1, int(cfg.get("max_commit_timestamps") or 20))
    log_args = ["log", "--pretty=format:%s|%cI", "-n", str(max_ct)]
    if since_hours and since_hours > 0:
        log_args.extend(["--since", f"{since_hours} hours ago"])
    ok_log, log_out = _run_git(p, log_args)
    commit_subjects: list[str] = []
    parsed_commit_times: list[datetime] = []
    if ok_log:
        rows = [x for x in log_out.splitlines() if x.strip()]
        for row in rows:
            subj, _, ts = row.partition("|")
            commit_subjects.append(subj.strip())
            dt = _parse_dt(ts.strip())
            if dt is not None:
                parsed_commit_times.append(dt)
        base["recent_commits_count"] = len(rows)
        base["recent_commit_subjects"] = commit_subjects[: int(cfg.get("max_commit_subjects") or 20)]
        if parsed_commit_times:
            base["last_commit_time"] = _fmt_z(parsed_commit_times[0])
            base["first_commit_time"] = _fmt_z(parsed_commit_times[-1])
        if bool(cfg.get("include_commit_timestamps", True)) and parsed_commit_times:
            base["commit_timestamps"] = [_fmt_z(x) for x in parsed_commit_times[:max_ct]]
    else:
        base["errors"].append(f"log:{log_out}")

    fws = _parse_dt(str(base.get("file_activity_window_start") or ""))
    fwe = _parse_dt(str(base.get("file_activity_window_end") or ""))
    cws = _parse_dt(str(base.get("first_commit_time") or ""))
    cwe = _parse_dt(str(base.get("last_commit_time") or ""))
    aw0, aw1 = _merge_activity_bounds(fws, fwe, cws, cwe)
    if aw0 is not None and aw1 is not None:
        base["activity_window_start"] = _fmt_z(aw0)
        base["activity_window_end"] = _fmt_z(aw1)

    base["has_remote"] = _git_has_remote(p)
    ahead, behind = _git_upstream_ahead_behind(p)
    base["branch_ahead"] = ahead
    base["branch_behind"] = behind
    base["push_needed"] = bool(ahead > 0)
    base["commit_needed"] = bool(
        int(base.get("uncommitted_changes_count") or 0) > 0 and base.get("file_activity_window_start")
    )
    uwa: float | None = None
    if fws is not None and int(base.get("uncommitted_changes_count") or 0) > 0:
        uwa = max(0.0, (_utc_now() - fws).total_seconds() / 3600.0)
    base["uncommitted_work_age_hours"] = round(uwa, 3) if uwa is not None else None
    clean_ish = int(base.get("uncommitted_changes_count") or 0) == 0
    base["git_hygiene_summary"] = _git_hygiene_summary_text(
        clean_ish=clean_ish,
        uncommitted=int(base.get("uncommitted_changes_count") or 0),
        ahead=ahead,
        commit_needed=bool(base["commit_needed"]),
        push_needed=bool(base["push_needed"]),
    )

    feature, area, stage = _infer_feature(p, str(base.get("current_branch") or ""))
    docs, tests, code, activity_type, intensity = _classify_activity(
        changed_files, int(base["recent_commits_count"]), base.get("last_commit_time")
    )
    base["docs_changed"] = docs
    base["tests_changed"] = tests
    base["code_changed"] = code
    base["likely_feature_name"] = feature
    base["feature_area"] = area
    base["rollout_stage"] = stage
    base["activity_type"] = activity_type
    base["activity_intensity"] = intensity
    if base["current_branch"] and str(base["current_branch"]).lower() != "main":
        base["linked_pr_guess"] = f"branch:{base['current_branch']}"
    quality = 1.0 - min(0.6, 0.2 * len(base["errors"]))
    signal = 0.4 + min(0.5, (base["changed_files_count"] + base["recent_commits_count"]) / 50.0)
    base["confidence"] = round(max(0.2, min(0.95, quality * signal)), 2)
    return base


def summarize_repo_activity(activity_list: list[dict[str, Any]]) -> dict[str, Any]:
    repos = len(activity_list)
    changed = [x for x in activity_list if int(x.get("changed_files_count") or 0) > 0 or int(x.get("recent_commits_count") or 0) > 0]
    high = [x for x in activity_list if str(x.get("activity_intensity")) == "high"]
    errors = sum(len(x.get("errors") or []) for x in activity_list)
    return {
        "repos_scanned": repos,
        "repos_with_activity": len(changed),
        "high_intensity_repos": len(high),
        "total_errors": errors,
    }


def build_repo_activity_progress_events(activity_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in activity_list:
        changed = int(row.get("changed_files_count") or 0)
        commits = int(row.get("recent_commits_count") or 0)
        if changed == 0 and commits == 0:
            continue
        summary = (
            f"{row.get('repo_name')}: {changed} changed files, {commits} recent commits "
            f"({row.get('activity_type')}/{row.get('activity_intensity')})"
        )
        events.append(
            {
                "type": "repo_activity",
                "repo_name": row.get("repo_name"),
                "feature_name": row.get("likely_feature_name"),
                "summary": summary,
                "activity_type": row.get("activity_type"),
                "activity_intensity": row.get("activity_intensity"),
                "branch": row.get("current_branch"),
                "evidence": [
                    f"git_status:{row.get('uncommitted_changes_count')}",
                    f"recent_commits:{row.get('recent_commits_count')}",
                ],
                "confidence": row.get("confidence", 0.5),
                "observed_at": row.get("observed_at"),
            }
        )
    return events


def _ingestion_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def collect_all_repo_activity(config: dict[str, Any]) -> dict[str, Any]:
    lane = (config or {}).get("repo_activity") or {}
    enabled = bool(lane.get("enabled", True))
    observed = _utc_now()
    if not enabled:
        out = {
            "activity_list": [],
            "summary": {"repos_scanned": 0, "repos_with_activity": 0, "high_intensity_repos": 0, "total_errors": 0},
            "progress_events": [],
            "errors": ["repo_activity_disabled"],
            "generated_at": now_iso(),
            "confidence": 0.3,
        }
        return out
    repo_roots = list(lane.get("repo_roots") or [])
    scan_depth = int(lane.get("scan_depth") or 2)
    since_hours = lane.get("since_hours")
    include_files = bool(lane.get("include_file_samples", True))
    max_file_samples = int(lane.get("max_file_samples") or 20)
    include_commits = bool(lane.get("include_commit_subjects", True))
    max_commit_subjects = int(lane.get("max_commit_subjects") or 20)

    repos = discover_local_repos(repo_roots, scan_depth)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    max_file_ts = int(lane.get("max_file_timestamp_samples") or 25)
    max_ct_lane = int(lane.get("max_commit_timestamps") or 20)
    for rp in repos:
        row = collect_repo_activity(rp, since_hours=since_hours if isinstance(since_hours, int) else None, lane=lane)
        if not include_files:
            row["changed_files_sample"] = []
        else:
            row["changed_files_sample"] = list(row.get("changed_files_sample") or [])[:max_file_samples]
        if not include_commits:
            row["recent_commit_subjects"] = []
        else:
            row["recent_commit_subjects"] = list(row.get("recent_commit_subjects") or [])[:max_commit_subjects]
        row["modified_file_timestamps_sample"] = list(row.get("modified_file_timestamps_sample") or [])[:max_file_ts]
        row["commit_timestamps"] = list(row.get("commit_timestamps") or [])[:max_ct_lane]
        rows.append(row)
        for e in row.get("errors") or []:
            errors.append(f"{rp.name}:{e}")
    summary = summarize_repo_activity(rows)
    progress = build_repo_activity_progress_events(rows)
    conf = 0.35
    if rows:
        conf = round(sum(float(r.get("confidence") or 0.0) for r in rows) / max(1, len(rows)), 2)
    out = {
        "activity_list": rows,
        "summary": summary,
        "progress_events": progress,
        "errors": errors,
        "generated_at": observed.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "confidence": conf,
    }
    return out


def build_repo_activity_snapshot(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = config or load_repo_activity_config()
    collected = collect_all_repo_activity(cfg)
    generated = _utc_now()
    source_tools = [
        "git status --short",
        "git log --pretty=format:%s|%cI",
        "git rev-parse --abbrev-ref HEAD",
        "os.stat mtime (changed paths only)",
        "git rev-list --left-right --count HEAD...@{upstream}",
    ]
    freshness_seconds = 300
    summary = collected.get("summary") or {}
    details = (
        f"Scanned {summary.get('repos_scanned', 0)} repos, "
        f"{summary.get('repos_with_activity', 0)} with activity, "
        f"{summary.get('high_intensity_repos', 0)} high intensity."
    )
    payload: dict[str, Any] = {
        "snapshot_type": "repo_activity_snapshot",
        "generated_at": generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freshness_seconds": freshness_seconds,
        "stale": False,
        "confidence": float(collected.get("confidence") or 0.4),
        "source_files_or_tools": source_tools,
        "missing_sources": [] if summary.get("repos_scanned", 0) > 0 else ["repo_roots"],
        "data": {
            "activity": collected.get("activity_list") or [],
            "summary": summary,
            "progress_events": collected.get("progress_events") or [],
        },
        "summary_short": f"Repo activity: {summary.get('repos_with_activity', 0)} active repos",
        "summary_detailed": details,
        "evidence_items": [
            {
                "title": "Local git metadata",
                "summary": details,
                "source_path_or_tool": "git",
                "observed_at": generated.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "confidence": float(collected.get("confidence") or 0.4),
            }
        ],
        "errors": list(collected.get("errors") or []),
    }
    out_path = _ingestion_dir() / "repo_activity_snapshot.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
