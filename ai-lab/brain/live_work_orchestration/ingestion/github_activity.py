"""
Phase 12 ingestion lane: GitHub PR and issue activity (read-only).

This module reads remote state and correlates it with local repo activity signals.
No GitHub write/comment/update operations are performed.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso
from brain.live_work_orchestration.ingestion.repo_activity import (
    _normalize_feature_name,
    _parse_simple_yaml,
    _utc_now,
)


def _default_config() -> dict[str, Any]:
    return {
        "github_activity": {
            "enabled": True,
            "repos": [],
            "include_prs": True,
            "include_issues": True,
            "include_closed_recent": False,
            "since_days": 14,
            "stale_pr_days": 7,
            "max_items_per_repo": 50,
        }
    }


def load_github_activity_config() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    c = root / "config" / "live_work_ingestion.yaml"
    if not c.is_file():
        c = root / "config" / "live_work_ingestion.example.yaml"
    merged = _default_config()
    loaded = _parse_simple_yaml(c)
    lane = loaded.get("github_activity") if isinstance(loaded, dict) else None
    if isinstance(lane, dict):
        merged["github_activity"].update(lane)
    return merged


def _run_gh(args: list[str]) -> tuple[bool, str]:
    try:
        p = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=20, check=False)
        return p.returncode == 0, (p.stdout or p.stderr or "").strip()
    except Exception as exc:
        return False, str(exc)


def determine_github_access_method() -> tuple[str, list[str]]:
    # Prefer existing connector if added in future.
    try:
        import brain.github_client  # type: ignore  # noqa: F401

        return "existing_connector", []
    except Exception:
        pass
    ok, _ = _run_gh(["--version"])
    if not ok:
        return "unavailable", ["gh_cli_unavailable"]
    auth_ok, auth_out = _run_gh(["auth", "status"])
    if not auth_ok:
        return "unavailable", [f"github_auth_unavailable:{auth_out[:200]}"]
    return "gh_cli", []


def _feature_area_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("docs", "readme", "wiki")):
        return "docs"
    if any(k in t for k in ("test", "qa", "spec")):
        return "testing"
    if any(k in t for k in ("infra", "ops", "deploy")):
        return "ops"
    return "core"


def _derive_review_state(reviews: list[dict[str, Any]]) -> str:
    if not reviews:
        return "not_reviewed"
    states = {str((r.get("state") or "")).upper() for r in reviews}
    if "CHANGES_REQUESTED" in states and "APPROVED" in states:
        return "mixed"
    if "CHANGES_REQUESTED" in states:
        return "changes_requested"
    if "APPROVED" in states:
        return "approved"
    if states:
        return "unknown"
    return "not_reviewed"


def _derive_checks_state(status_rollup: Any) -> str:
    if not status_rollup:
        return "unknown"
    text = json.dumps(status_rollup).lower()
    if "failure" in text or "failed" in text or '"conclusion":"failure"' in text:
        return "failing"
    if "pending" in text or "in_progress" in text:
        return "pending"
    if "success" in text or '"conclusion":"success"' in text:
        return "passing"
    return "unknown"


def _derive_pr_rollout_stage(pr: dict[str, Any], review_state: str, checks_state: str) -> str:
    if pr.get("mergedAt"):
        return "merged"
    state = str(pr.get("state") or "").upper()
    draft = bool(pr.get("isDraft"))
    if state == "CLOSED":
        return "unknown"
    if review_state == "changes_requested" or checks_state == "failing":
        return "blocked"
    if draft:
        return "dev"
    if review_state == "approved" and checks_state in ("passing", "unknown"):
        return "ready_to_merge"
    if review_state in ("not_reviewed", "unknown", "mixed") or checks_state == "pending":
        return "review"
    return "unknown"


def _age_days(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return max(0.0, (_utc_now() - dt).total_seconds() / 86400.0)
    except Exception:
        return None


def _feature_similarity(a: str, b: str) -> float:
    aa = {x for x in (a or "").replace("-", " ").replace("/", " ").lower().split() if x}
    bb = {x for x in (b or "").replace("-", " ").replace("/", " ").lower().split() if x}
    if not aa or not bb:
        return 0.0
    inter = len(aa.intersection(bb))
    union = len(aa.union(bb))
    return inter / union if union else 0.0


def _priority_guess(issue: dict[str, Any]) -> str:
    text = (str(issue.get("title") or "") + " " + " ".join(issue.get("labels") or [])).lower()
    if any(k in text for k in ("p0", "critical", "urgent", "high")):
        return "high"
    if any(k in text for k in ("p2", "low", "nice to have", "backlog")):
        return "low"
    if text:
        return "medium"
    return "unknown"


def _extract_linked_issues(text: str) -> list[str]:
    out: list[str] = []
    for tok in (text or "").replace(",", " ").split():
        if tok.startswith("#") and tok[1:].isdigit():
            out.append(tok)
    return out


def _fetch_repo_graphql(owner: str, name: str, max_items: int, since_days: int, include_prs: bool, include_issues: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    prs_raw: list[dict[str, Any]] = []
    issues_raw: list[dict[str, Any]] = []
    if include_prs:
        query_pr = (
            "query($owner:String!,$name:String!,$n:Int!){"
            "repository(owner:$owner,name:$name){pullRequests(first:$n,orderBy:{field:UPDATED_AT,direction:DESC},states:[OPEN,MERGED,CLOSED]){nodes{"
            "number title url state isDraft createdAt updatedAt mergedAt "
            "author{login} baseRefName headRefName changedFiles labels(first:20){nodes{name}} "
            "reviewRequests(first:20){nodes{requestedReviewer{... on User{login} ... on Team{name}}}} "
            "reviews(first:20){nodes{state author{login}}} "
            "closingIssuesReferences(first:20){nodes{number url title}} "
            "commits(last:1){totalCount nodes{commit{statusCheckRollup}}}"
            "}}}}"
        )
        vars_payload = json.dumps({"owner": owner, "name": name, "n": max_items})
        ok, out = _run_gh(["api", "graphql", "-f", f"query={query_pr}", "-f", f"variables={vars_payload}"])
        if ok:
            try:
                payload = json.loads(out)
                prs_raw = (((payload.get("data") or {}).get("repository") or {}).get("pullRequests") or {}).get("nodes") or []
            except Exception as exc:
                errors.append(f"pr_parse_error:{exc}")
        else:
            errors.append(f"pr_fetch_error:{out[:250]}")
    if include_issues:
        query_issue = (
            "query($owner:String!,$name:String!,$n:Int!){"
            "repository(owner:$owner,name:$name){issues(first:$n,orderBy:{field:UPDATED_AT,direction:DESC},states:[OPEN,CLOSED]){nodes{"
            "number title url state createdAt updatedAt author{login} "
            "labels(first:20){nodes{name}} assignees(first:20){nodes{login}} milestone{title} "
            "timelineItems(first:20,itemTypes:[CROSS_REFERENCED_EVENT]){nodes{... on CrossReferencedEvent{source{__typename ... on PullRequest{number url title}}}}}"
            "}}}}"
        )
        vars_payload = json.dumps({"owner": owner, "name": name, "n": max_items})
        ok, out = _run_gh(["api", "graphql", "-f", f"query={query_issue}", "-f", f"variables={vars_payload}"])
        if ok:
            try:
                payload = json.loads(out)
                issues_raw = (((payload.get("data") or {}).get("repository") or {}).get("issues") or {}).get("nodes") or []
            except Exception as exc:
                errors.append(f"issue_parse_error:{exc}")
        else:
            errors.append(f"issue_fetch_error:{out[:250]}")
    # since_days filter at normalization stage
    return prs_raw, issues_raw, errors


def _is_recent(ts: str | None, since_days: int) -> bool:
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        age = (_utc_now() - dt).total_seconds() / 86400.0
        return age <= max(1, since_days)
    except Exception:
        return True


def _normalize_pr(owner: str, repo: str, pr: dict[str, Any], include_closed_recent: bool, since_days: int) -> dict[str, Any] | None:
    state = str(pr.get("state") or "").lower()
    updated_at = str(pr.get("updatedAt") or "")
    if state != "open" and not include_closed_recent and not _is_recent(updated_at, since_days):
        return None
    labels = [str(x.get("name")) for x in (((pr.get("labels") or {}).get("nodes")) or []) if isinstance(x, dict)]
    reviewers: list[str] = []
    for n in (((pr.get("reviewRequests") or {}).get("nodes")) or []):
        rr = (n.get("requestedReviewer") or {}) if isinstance(n, dict) else {}
        if rr.get("login"):
            reviewers.append(str(rr.get("login")))
        elif rr.get("name"):
            reviewers.append(str(rr.get("name")))
    reviews = [x for x in (((pr.get("reviews") or {}).get("nodes")) or []) if isinstance(x, dict)]
    review_state = _derive_review_state(reviews)
    rollup = None
    commits = (((pr.get("commits") or {}).get("nodes")) or [])
    if commits and isinstance(commits[0], dict):
        rollup = ((commits[0].get("commit") or {}).get("statusCheckRollup"))
    checks_state = _derive_checks_state(rollup)
    title = str(pr.get("title") or "")
    head = str(pr.get("headRefName") or "")
    feature_name = _normalize_feature_name(head or title, repo)
    linked = [f"#{x.get('number')}" for x in (((pr.get("closingIssuesReferences") or {}).get("nodes")) or []) if isinstance(x, dict)]
    blockers: list[str] = []
    blocker_types: list[str] = []
    if review_state == "changes_requested":
        blockers.append("changes_requested")
        blocker_types.append("review")
    if checks_state == "failing":
        blockers.append("checks_failing")
        blocker_types.append("checks")
    if bool(pr.get("isDraft")):
        blockers.append("draft")
        blocker_types.append("unknown")
    if any("depend" in x.lower() for x in labels):
        blocker_types.append("dependency")
    rollout_stage = _derive_pr_rollout_stage(pr, review_state, checks_state)
    return {
        "repo_name": repo,
        "repo_owner": owner,
        "pr_number": int(pr.get("number") or 0),
        "title": title,
        "url": str(pr.get("url") or ""),
        "state": state,
        "draft": bool(pr.get("isDraft")),
        "author": str((pr.get("author") or {}).get("login") or ""),
        "base_branch": str(pr.get("baseRefName") or ""),
        "head_branch": head,
        "created_at": str(pr.get("createdAt") or ""),
        "updated_at": updated_at,
        "merged_at": str(pr.get("mergedAt") or "") or None,
        "labels": labels,
        "reviewers": reviewers,
        "review_state": review_state,
        "checks_state": checks_state,
        "changed_files_count": int(pr.get("changedFiles") or 0),
        "recent_commits_count": int(((pr.get("commits") or {}).get("totalCount")) or 0),
        "linked_issues": linked,
        "likely_feature_name": feature_name,
        "feature_area": _feature_area_from_text(title + " " + head + " " + " ".join(labels)),
        "rollout_stage": rollout_stage,
        "blockers": blockers,
        "blocker_types": sorted(set(blocker_types)) or ["unknown"],
        "confidence": 0.8 if int(pr.get("number") or 0) > 0 else 0.4,
        "evidence": ["gh_api_graphql_pull_request"],
    }


def _normalize_issue(owner: str, repo: str, issue: dict[str, Any], include_closed_recent: bool, since_days: int) -> dict[str, Any] | None:
    state = str(issue.get("state") or "").lower()
    updated_at = str(issue.get("updatedAt") or "")
    if state != "open" and not include_closed_recent and not _is_recent(updated_at, since_days):
        return None
    labels = [str(x.get("name")) for x in (((issue.get("labels") or {}).get("nodes")) or []) if isinstance(x, dict)]
    assignees = [str(x.get("login")) for x in (((issue.get("assignees") or {}).get("nodes")) or []) if isinstance(x, dict)]
    linked_prs: list[str] = []
    for n in (((issue.get("timelineItems") or {}).get("nodes")) or []):
        if not isinstance(n, dict):
            continue
        src = n.get("source") or {}
        if isinstance(src, dict) and src.get("__typename") == "PullRequest":
            linked_prs.append(str(src.get("url") or ""))
    blocker_flags: list[str] = []
    txt = (str(issue.get("title") or "") + " " + " ".join(labels)).lower()
    if any(k in txt for k in ("blocked", "blocker", "dependency")):
        blocker_flags.append("blocked")
    return {
        "repo_name": repo,
        "repo_owner": owner,
        "issue_number": int(issue.get("number") or 0),
        "title": str(issue.get("title") or ""),
        "url": str(issue.get("url") or ""),
        "state": state,
        "author": str((issue.get("author") or {}).get("login") or ""),
        "labels": labels,
        "assignees": assignees,
        "created_at": str(issue.get("createdAt") or ""),
        "updated_at": updated_at,
        "milestone": str((issue.get("milestone") or {}).get("title") or "") or None,
        "linked_prs": linked_prs,
        "blocker_flags": blocker_flags,
        "feature_area": _feature_area_from_text(str(issue.get("title") or "") + " " + " ".join(labels)),
        "priority_guess": _priority_guess({"title": issue.get("title"), "labels": labels}),
        "confidence": 0.78 if int(issue.get("number") or 0) > 0 else 0.4,
        "evidence": ["gh_api_graphql_issue"],
    }


def collect_github_activity(config: dict[str, Any], *, mock_data: dict[str, Any] | None = None) -> dict[str, Any]:
    lane = (config or {}).get("github_activity") or {}
    enabled = bool(lane.get("enabled", True))
    if not enabled:
        return {"prs": [], "issues": [], "errors": ["github_activity_disabled"], "missing_sources": [], "stale": False}
    repos = list(lane.get("repos") or [])
    include_prs = bool(lane.get("include_prs", True))
    include_issues = bool(lane.get("include_issues", True))
    include_closed_recent = bool(lane.get("include_closed_recent", False))
    since_days = int(lane.get("since_days") or 14)
    max_items = int(lane.get("max_items_per_repo") or 50)

    method, access_errors = determine_github_access_method()
    if mock_data is not None:
        method = "mock_data"
        access_errors = []
    if method == "unavailable" and mock_data is None:
        return {
            "prs": [],
            "issues": [],
            "errors": access_errors,
            "missing_sources": ["github_access_unavailable"],
            "stale": True,
            "source_files_or_tools": [],
        }

    prs: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    errors: list[str] = []
    source_tools: list[str] = ["github:read_only"]
    for repo_cfg in repos:
        if not isinstance(repo_cfg, dict):
            continue
        owner = str(repo_cfg.get("owner") or "")
        name = str(repo_cfg.get("name") or "")
        if not owner or not name:
            errors.append("repo_config_missing_owner_or_name")
            continue
        if mock_data is not None:
            repo_blob = (mock_data.get(f"{owner}/{name}") or {}) if isinstance(mock_data, dict) else {}
            prs_raw = list(repo_blob.get("prs") or [])
            issues_raw = list(repo_blob.get("issues") or [])
            fetch_errors: list[str] = []
        else:
            prs_raw, issues_raw, fetch_errors = _fetch_repo_graphql(
                owner, name, max_items, since_days, include_prs, include_issues
            )
            source_tools.append(f"gh_api:repo:{owner}/{name}")
        errors.extend(fetch_errors)
        for pr in prs_raw:
            if not isinstance(pr, dict):
                continue
            row = _normalize_pr(owner, name, pr, include_closed_recent, since_days)
            if row:
                prs.append(row)
        for issue in issues_raw:
            if not isinstance(issue, dict):
                continue
            row = _normalize_issue(owner, name, issue, include_closed_recent, since_days)
            if row:
                issues.append(row)
    return {
        "prs": prs,
        "issues": issues,
        "errors": errors,
        "missing_sources": [],
        "stale": False,
        "source_files_or_tools": source_tools,
    }


def correlate_github_with_repo_activity(
    github_snapshot: dict[str, Any], repo_activity_snapshot: dict[str, Any] | None, *, stale_pr_days: int = 7
) -> dict[str, Any]:
    g_data = github_snapshot.get("data") if isinstance(github_snapshot.get("data"), dict) else github_snapshot
    prs = list((g_data.get("prs") or [])) if isinstance(g_data, dict) else []
    issues = list((g_data.get("issues") or [])) if isinstance(g_data, dict) else []
    repo_data = (repo_activity_snapshot.get("data") or {}) if isinstance(repo_activity_snapshot, dict) else {}
    local_rows = list(repo_data.get("activity") or [])

    feature_states: list[dict[str, Any]] = []
    local_without_pr = 0
    open_pr_without_local = 0
    blocked_prs = 0
    matched = 0

    # Index PRs by head and feature.
    pr_by_head: dict[str, dict[str, Any]] = {}
    pr_by_feature: dict[str, dict[str, Any]] = {}
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        pr_by_head[str(pr.get("head_branch") or "").lower()] = pr
        pr_by_feature[str(pr.get("likely_feature_name") or "").lower()] = pr
        if str(pr.get("rollout_stage")) == "blocked":
            blocked_prs += 1

    for row in local_rows:
        if not isinstance(row, dict):
            continue
        branch = str(row.get("current_branch") or "").lower()
        feat = str(row.get("likely_feature_name") or "").lower()
        pr_branch = pr_by_head.get(branch)
        pr_feature = pr_by_feature.get(feat) if not pr_branch else None
        pr = pr_branch or pr_feature
        correlation_confidence = "low"
        issue_refs: list[str] = []
        blockers: list[str] = []
        blocker_types: list[str] = []
        linked_pr: str | None = None
        rollout_stage = str(row.get("rollout_stage") or "unknown")
        next_action = "continue_local_work"
        conf = float(row.get("confidence") or 0.5)
        if pr:
            matched += 1
            if pr_branch:
                correlation_confidence = "high"
            elif pr_feature:
                sim = _feature_similarity(feat, str((pr_feature.get("likely_feature_name") or pr_feature.get("title") or "")))
                correlation_confidence = "medium" if sim >= 0.35 else "low"
            linked_pr = pr.get("url")
            issue_refs = list(pr.get("linked_issues") or [])
            blockers.extend(list(pr.get("blockers") or []))
            blocker_types.extend(list(pr.get("blocker_types") or []))
            rollout_stage = str(pr.get("rollout_stage") or rollout_stage)
            next_action = "address_pr_feedback" if blockers else ("merge_when_ready" if rollout_stage == "ready_to_merge" else "progress_pr")
            if correlation_confidence == "high":
                conf = min(0.95, conf + 0.25)
            elif correlation_confidence == "medium":
                conf = min(0.9, conf + 0.15)
            else:
                conf = min(0.85, conf + 0.08)
        else:
            local_without_pr += 1
            blockers.append("no_remote_pr")
            blocker_types.append("unknown")
            next_action = "open_or_link_pr"
        feature_states.append(
            {
                "feature_name": row.get("likely_feature_name") or row.get("repo_name"),
                "repo_name": row.get("repo_name"),
                "local_activity_present": True,
                "linked_pr": linked_pr,
                "issue_refs": issue_refs,
                "rollout_stage": rollout_stage,
                "blockers": blockers,
                "blocker_type": sorted(set(blocker_types)) or ["unknown"],
                "next_action": next_action,
                "correlation_confidence": correlation_confidence,
                "confidence": round(conf, 2),
                "evidence": [f"local_branch:{row.get('current_branch')}", f"pr_head_match:{bool(pr)}"],
            }
        )

    local_branch_set = {str(x.get("current_branch") or "").lower() for x in local_rows if isinstance(x, dict)}
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        if str(pr.get("state")) != "open":
            continue
        head = str(pr.get("head_branch") or "").lower()
        if head and head not in local_branch_set:
            open_pr_without_local += 1
            stale_by_age = False
            age = _age_days(str(pr.get("updated_at") or ""))
            if age is not None:
                stale_by_age = (int(pr.get("recent_commits_count") or 0) == 0) and (age >= max(1, stale_pr_days))
            blockers = list(pr.get("blockers") or []) + ["no_recent_local_activity"]
            if stale_by_age:
                blockers.append("stale_remote_pr")
            feature_states.append(
                {
                    "feature_name": pr.get("likely_feature_name") or pr.get("title"),
                    "repo_name": pr.get("repo_name"),
                    "local_activity_present": False,
                    "linked_pr": pr.get("url"),
                    "issue_refs": list(pr.get("linked_issues") or []),
                    "rollout_stage": pr.get("rollout_stage") or "review",
                    "blockers": blockers,
                    "blocker_type": sorted(set(list(pr.get("blocker_types") or []) + ["unknown"])),
                    "next_action": "review_or_rebase",
                    "correlation_confidence": "low",
                    "confidence": round(float(pr.get("confidence") or 0.6), 2),
                    "evidence": [f"pr_head:{pr.get('head_branch')}", "local_activity:false"],
                }
            )

    # Attach issue refs by text match fallback.
    for st in feature_states:
        feat = str(st.get("feature_name") or "").lower()
        extra_refs: list[str] = []
        for iss in issues:
            if not isinstance(iss, dict):
                continue
            title = str(iss.get("title") or "").lower()
            if feat and feat in title:
                extra_refs.append(f"#{iss.get('issue_number')}")
        if extra_refs:
            st["issue_refs"] = sorted(set(list(st.get("issue_refs") or []) + extra_refs))
            if str(st.get("rollout_stage")) == "unknown":
                st["rollout_stage"] = "dev"

    return {
        "feature_states": feature_states,
        "correlation_summary": {
            "local_activity_total": len(local_rows),
            "local_with_pr_match": matched,
            "local_without_pr": local_without_pr,
            "open_pr_without_local_activity": open_pr_without_local,
            "blocked_prs": blocked_prs,
        },
    }


def _ingestion_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def build_github_activity_snapshot(
    config: dict[str, Any] | None = None,
    *,
    repo_activity_snapshot: dict[str, Any] | None = None,
    mock_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config or load_github_activity_config()
    collected = collect_github_activity(cfg, mock_data=mock_data)
    generated = _utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")
    if repo_activity_snapshot is None:
        rp = _ingestion_dir() / "repo_activity_snapshot.json"
        if rp.is_file():
            try:
                repo_activity_snapshot = json.loads(rp.read_text(encoding="utf-8"))
            except Exception:
                repo_activity_snapshot = None
    corr = correlate_github_with_repo_activity(
        {"data": {"prs": collected.get("prs") or [], "issues": collected.get("issues") or []}},
        repo_activity_snapshot,
        stale_pr_days=int(((cfg.get("github_activity") or {}).get("stale_pr_days") or 7)),
    )
    summary = corr.get("correlation_summary") or {}
    stale = bool(collected.get("stale"))
    missing_sources = list(collected.get("missing_sources") or [])
    errors = list(collected.get("errors") or [])
    prs = list(collected.get("prs") or [])
    issues = list(collected.get("issues") or [])
    feature_states = list(corr.get("feature_states") or [])
    confidence = 0.35 if stale else 0.75
    if feature_states:
        confidence = min(0.92, confidence + 0.08)
    payload = {
        "snapshot_type": "github_activity_snapshot",
        "generated_at": generated,
        "freshness_seconds": 600,
        "stale": stale,
        "confidence": confidence,
        "source_files_or_tools": list(collected.get("source_files_or_tools") or []),
        "missing_sources": missing_sources,
        "data": {
            "prs": prs,
            "issues": issues,
            "feature_states": feature_states,
            "correlation_summary": summary,
        },
        "summary_short": f"GitHub activity: {len(prs)} PRs, {len(issues)} issues, {len(feature_states)} feature states",
        "summary_detailed": (
            f"Matched {summary.get('local_with_pr_match', 0)} local features to PRs; "
            f"{summary.get('blocked_prs', 0)} blocked PRs; "
            f"{summary.get('open_pr_without_local_activity', 0)} open PRs with no recent local activity."
        ),
        "evidence_items": [
            {
                "title": "GitHub read-only ingestion",
                "summary": "PR and issue metadata collected with no write operations.",
                "source_path_or_tool": "gh api graphql",
                "observed_at": generated,
                "confidence": confidence,
            }
        ],
        "errors": errors,
    }
    out = _ingestion_dir() / "github_activity_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
