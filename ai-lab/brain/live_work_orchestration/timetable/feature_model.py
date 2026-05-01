from __future__ import annotations

from typing import Any


def build_feature_states(
    repo_activity_snapshot: dict[str, Any] | None,
    github_activity_snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Build normalized feature states from Phase 11 + Phase 12 snapshots."""
    repo_data = (repo_activity_snapshot or {}).get("data") or {}
    gh_data = (github_activity_snapshot or {}).get("data") or {}
    repo_rows = list(repo_data.get("activity") or [])
    gh_features = list(gh_data.get("feature_states") or [])

    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for fs in gh_features:
        if not isinstance(fs, dict):
            continue
        name = str(fs.get("feature_name") or "").strip() or "unknown_feature"
        repo = str(fs.get("repo_name") or "").strip() or "unknown_repo"
        key = (repo.lower(), name.lower())
        seen.add(key)
        out.append(
            {
                "feature_name": name,
                "repo_name": repo,
                "local_activity_present": bool(fs.get("local_activity_present")),
                "linked_pr": fs.get("linked_pr"),
                "issue_refs": list(fs.get("issue_refs") or []),
                "rollout_stage": str(fs.get("rollout_stage") or "unknown"),
                "blockers": list(fs.get("blockers") or []),
                "blocker_type": list(fs.get("blocker_type") or ["unknown"]),
                "next_action": str(fs.get("next_action") or "clarify_scope"),
                "activity_intensity": str(fs.get("activity_intensity") or "low"),
                "activity_type": str(fs.get("activity_type") or "mixed"),
                "changed_files_count": int(fs.get("changed_files_count") or 0),
                "recent_commits_count": int(fs.get("recent_commits_count") or 0),
                "confidence": float(fs.get("confidence") or 0.5),
                "evidence": list(fs.get("evidence") or []),
            }
        )

    for row in repo_rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("likely_feature_name") or row.get("repo_name") or "unknown_feature")
        repo = str(row.get("repo_name") or "unknown_repo")
        key = (repo.lower(), name.lower())
        if key in seen:
            continue
        out.append(
            {
                "feature_name": name,
                "repo_name": repo,
                "local_activity_present": True,
                "linked_pr": row.get("linked_pr_guess"),
                "issue_refs": [],
                "rollout_stage": str(row.get("rollout_stage") or "unknown"),
                "blockers": ["no_remote_pr"] if not row.get("linked_pr_guess") else [],
                "blocker_type": ["unknown"] if not row.get("linked_pr_guess") else [],
                "next_action": "open_or_link_pr" if not row.get("linked_pr_guess") else "continue_local_work",
                "activity_intensity": str(row.get("activity_intensity") or "low"),
                "activity_type": str(row.get("activity_type") or "mixed"),
                "changed_files_count": int(row.get("changed_files_count") or 0),
                "recent_commits_count": int(row.get("recent_commits_count") or 0),
                "confidence": float(row.get("confidence") or 0.45),
                "evidence": [f"local_branch:{row.get('current_branch')}"],
            }
        )
    return out

