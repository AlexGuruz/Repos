from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.live_work_orchestration.builders import build_daily_progress_snapshot
from brain.live_work_orchestration.compiler import compile_daily_plan_preview
from brain.live_work_orchestration.ingestion import github_activity


def _cfg() -> dict:
    return {
        "github_activity": {
            "enabled": True,
            "repos": [{"owner": "acme", "name": "ai-lab", "local_path": "E:/Repos/ai-lab"}],
            "include_prs": True,
            "include_issues": True,
            "include_closed_recent": True,
            "since_days": 14,
            "max_items_per_repo": 50,
        }
    }


def _mock_graphql_data() -> dict:
    return {
        "acme/ai-lab": {
            "prs": [
                {
                    "number": 12,
                    "title": "feat: improve planner lane",
                    "url": "https://github.com/acme/ai-lab/pull/12",
                    "state": "OPEN",
                    "isDraft": False,
                    "createdAt": "2026-04-28T10:00:00Z",
                    "updatedAt": "2026-04-30T08:00:00Z",
                    "mergedAt": None,
                    "author": {"login": "dev1"},
                    "baseRefName": "main",
                    "headRefName": "feature/planner-lane",
                    "changedFiles": 7,
                    "labels": {"nodes": [{"name": "enhancement"}]},
                    "reviewRequests": {"nodes": [{"requestedReviewer": {"login": "reviewer1"}}]},
                    "reviews": {"nodes": [{"state": "APPROVED", "author": {"login": "reviewer1"}}]},
                    "closingIssuesReferences": {"nodes": [{"number": 88, "url": "u", "title": "issue"}]},
                    "commits": {"totalCount": 3, "nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
                },
                {
                    "number": 22,
                    "title": "fix flaky build",
                    "url": "https://github.com/acme/ai-lab/pull/22",
                    "state": "OPEN",
                    "isDraft": False,
                    "createdAt": "2026-04-27T09:00:00Z",
                    "updatedAt": "2026-01-01T07:00:00Z",
                    "mergedAt": None,
                    "author": {"login": "dev2"},
                    "baseRefName": "main",
                    "headRefName": "fix/flaky-build",
                    "changedFiles": 3,
                    "labels": {"nodes": [{"name": "bug"}]},
                    "reviewRequests": {"nodes": []},
                    "reviews": {"nodes": [{"state": "CHANGES_REQUESTED", "author": {"login": "rev2"}}]},
                    "closingIssuesReferences": {"nodes": []},
                    "commits": {"totalCount": 0, "nodes": [{"commit": {"statusCheckRollup": {"state": "FAILURE"}}}]},
                },
            ],
            "issues": [
                {
                    "number": 88,
                    "title": "planner lane cleanup",
                    "url": "https://github.com/acme/ai-lab/issues/88",
                    "state": "OPEN",
                    "createdAt": "2026-04-25T01:00:00Z",
                    "updatedAt": "2026-04-30T07:00:00Z",
                    "author": {"login": "pm1"},
                    "labels": {"nodes": [{"name": "high"}]},
                    "assignees": {"nodes": [{"login": "dev1"}]},
                    "milestone": {"title": "M1"},
                    "timelineItems": {
                        "nodes": [{"source": {"__typename": "PullRequest", "number": 12, "url": "https://github.com/acme/ai-lab/pull/12", "title": "x"}}]
                    },
                }
            ],
        }
    }


def test_handles_missing_github_access_gracefully(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.github_activity.determine_github_access_method", lambda: ("unavailable", ["x"]))
    out = github_activity.collect_github_activity(_cfg())
    assert out["stale"] is True
    assert "github_access_unavailable" in out["missing_sources"]


def test_parses_pr_fixture_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.github_activity.determine_github_access_method", lambda: ("gh_cli", []))
    out = github_activity.collect_github_activity(_cfg(), mock_data=_mock_graphql_data())
    assert len(out["prs"]) >= 2
    assert out["prs"][0]["pr_number"] == 12
    assert "blocker_types" in out["prs"][0]


def test_parses_issue_fixture_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.github_activity.determine_github_access_method", lambda: ("gh_cli", []))
    out = github_activity.collect_github_activity(_cfg(), mock_data=_mock_graphql_data())
    assert len(out["issues"]) == 1
    assert out["issues"][0]["issue_number"] == 88


def test_derives_review_state() -> None:
    assert github_activity._derive_review_state([]) == "not_reviewed"
    assert github_activity._derive_review_state([{"state": "APPROVED"}]) == "approved"
    assert github_activity._derive_review_state([{"state": "CHANGES_REQUESTED"}]) == "changes_requested"


def test_derives_checks_state() -> None:
    assert github_activity._derive_checks_state({"state": "SUCCESS"}) == "passing"
    assert github_activity._derive_checks_state({"state": "FAILURE"}) == "failing"
    assert github_activity._derive_checks_state({"state": "PENDING"}) == "pending"


def test_derives_rollout_stage() -> None:
    pr = {"state": "OPEN", "isDraft": False, "mergedAt": None}
    assert github_activity._derive_pr_rollout_stage(pr, "approved", "passing") == "ready_to_merge"
    assert github_activity._derive_pr_rollout_stage(pr, "changes_requested", "passing") == "blocked"


def test_correlates_local_branch_to_pr_head_branch() -> None:
    gh = {"data": {"prs": [{"head_branch": "feature/planner-lane", "url": "u", "linked_issues": [], "rollout_stage": "review", "blockers": [], "blocker_types": ["unknown"]}], "issues": []}}
    repo = {"data": {"activity": [{"repo_name": "ai-lab", "current_branch": "feature/planner-lane", "likely_feature_name": "planner-lane", "rollout_stage": "dev", "confidence": 0.6}]}}
    out = github_activity.correlate_github_with_repo_activity(gh, repo)
    fs = out["feature_states"][0]
    assert fs["linked_pr"] == "u"
    assert fs["correlation_confidence"] == "high"


def test_flags_local_activity_without_pr() -> None:
    gh = {"data": {"prs": [], "issues": []}}
    repo = {"data": {"activity": [{"repo_name": "ai-lab", "current_branch": "feature/no-pr", "likely_feature_name": "no-pr", "rollout_stage": "dev", "confidence": 0.6}]}}
    out = github_activity.correlate_github_with_repo_activity(gh, repo)
    assert out["correlation_summary"]["local_without_pr"] == 1


def test_flags_open_pr_with_no_recent_local_activity() -> None:
    gh = {
        "data": {
            "prs": [
                {
                    "state": "open",
                    "head_branch": "feature/x",
                    "url": "u",
                    "repo_name": "ai-lab",
                    "likely_feature_name": "x",
                    "linked_issues": [],
                    "rollout_stage": "review",
                    "blockers": [],
                    "blocker_types": ["unknown"],
                    "updated_at": "2026-01-01T00:00:00Z",
                    "recent_commits_count": 0,
                }
            ],
            "issues": [],
        }
    }
    repo = {"data": {"activity": []}}
    out = github_activity.correlate_github_with_repo_activity(gh, repo)
    assert out["correlation_summary"]["open_pr_without_local_activity"] == 1
    assert "stale_remote_pr" in (out["feature_states"][0].get("blockers") or [])


def test_writes_github_activity_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.github_activity._ingestion_dir", lambda: tmp_path / "ingestion")
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.github_activity.determine_github_access_method", lambda: ("gh_cli", []))
    snap = github_activity.build_github_activity_snapshot(_cfg(), mock_data=_mock_graphql_data())
    assert snap["snapshot_type"] == "github_activity_snapshot"
    assert (tmp_path / "ingestion" / "github_activity_snapshot.json").is_file()


def test_daily_progress_includes_github_feature_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    ing = tmp_path / "ingestion"
    ing.mkdir(parents=True, exist_ok=True)
    (ing / "repo_activity_snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_type": "repo_activity_snapshot",
                "generated_at": "2026-01-01T00:00:00Z",
                "freshness_seconds": 300,
                "stale": False,
                "confidence": 0.8,
                "source_files_or_tools": ["git"],
                "missing_sources": [],
                "data": {"activity": [], "summary": {}, "progress_events": []},
                "summary_short": "s",
                "summary_detailed": "d",
                "evidence_items": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    (ing / "github_activity_snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_type": "github_activity_snapshot",
                "generated_at": "2026-01-01T00:00:00Z",
                "freshness_seconds": 600,
                "stale": False,
                "confidence": 0.8,
                "source_files_or_tools": ["gh"],
                "missing_sources": [],
                "data": {
                    "prs": [],
                    "issues": [],
                    "feature_states": [
                        {
                            "feature_name": "planner-lane",
                            "repo_name": "ai-lab",
                            "local_activity_present": True,
                            "linked_pr": "u",
                            "issue_refs": [],
                            "rollout_stage": "review",
                            "blockers": ["changes_requested"],
                            "next_action": "address_pr_feedback",
                            "confidence": 0.8,
                            "evidence": ["x"],
                        }
                    ],
                    "correlation_summary": {"local_with_pr_match": 1, "local_without_pr": 0, "open_pr_without_local_activity": 0, "blocked_prs": 1},
                },
                "summary_short": "s",
                "summary_detailed": "d",
                "evidence_items": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    out = build_daily_progress_snapshot()
    data = out.get("data") or {}
    assert len(data.get("github_feature_states") or []) == 1
    assert len(data.get("github_blockers") or []) == 1


def test_compiler_mentions_pr_blocker_signals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    # Minimal snapshots
    (tmp_path / "work_demand_snapshot.json").write_text(
        json.dumps({"data": {"demands": []}, "confidence": 0.8, "missing_sources": []}), encoding="utf-8"
    )
    (tmp_path / "time_constraints_snapshot.json").write_text(
        json.dumps({"data": {"constraints": []}, "confidence": 0.8, "missing_sources": []}), encoding="utf-8"
    )
    (tmp_path / "planning_gaps_snapshot.json").write_text(json.dumps({"data": {"gaps": []}}), encoding="utf-8")
    (tmp_path / "communication_queue_snapshot.json").write_text(json.dumps({"data": {"items": []}}), encoding="utf-8")
    (tmp_path / "daily_progress_snapshot.json").write_text(
        json.dumps(
            {
                "data": {
                    "events": [],
                    "repo_activity_rows": [],
                    "repo_activity_ingestion_summary": {},
                    "github_feature_states": [{"rollout_stage": "ready_to_merge"}],
                    "github_remote_summary": {"local_with_pr_match": 1, "local_without_pr": 1, "open_pr_without_local_activity": 1},
                    "github_blockers": [{"feature_name": "x", "blockers": ["changes_requested"]}],
                }
            }
        ),
        encoding="utf-8",
    )
    prev = compile_daily_plan_preview(include_action_recommendations=False)
    blob = json.dumps(prev).lower()
    assert "github blockers detected" in blob
    assert "ready to merge" in blob


def test_no_github_write_or_comment_calls_exist() -> None:
    src = Path(github_activity.__file__).read_text(encoding="utf-8").lower()
    assert "issues/" not in src or "comments" not in src
    assert "patch" not in src
    assert "post" not in src
