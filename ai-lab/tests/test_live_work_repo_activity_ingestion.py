from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from brain.live_work_orchestration.builders import build_daily_progress_snapshot
from brain.live_work_orchestration.ingestion import repo_activity


def _mk_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True, text=True)
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-c", "user.name=bot", "-c", "user.email=bot@example.com", "commit", "-m", "init repo"],
        cwd=str(path),
        check=True,
        capture_output=True,
        text=True,
    )


def test_detects_git_repo(tmp_path: Path) -> None:
    rp = tmp_path / "repo-a"
    _mk_git_repo(rp)
    repos = repo_activity.discover_local_repos([str(tmp_path)], scan_depth=2)
    assert any(Path(x).name == "repo-a" for x in repos)


def test_handles_non_git_paths_safely(tmp_path: Path) -> None:
    ng = tmp_path / "not-git"
    ng.mkdir()
    out = repo_activity.collect_repo_activity(ng)
    assert "not_a_git_repo" in (out.get("errors") or [])


def test_collects_changed_file_counts(tmp_path: Path) -> None:
    rp = tmp_path / "repo-b"
    _mk_git_repo(rp)
    (rp / "src.py").write_text("print('x')\n", encoding="utf-8")
    out = repo_activity.collect_repo_activity(rp)
    assert out["changed_files_count"] >= 1
    assert out["uncommitted_changes_count"] >= 1


def test_collects_commit_summaries(tmp_path: Path) -> None:
    rp = tmp_path / "repo-c"
    _mk_git_repo(rp)
    out = repo_activity.collect_repo_activity(rp, since_hours=72)
    assert out["recent_commits_count"] >= 1
    assert isinstance(out["recent_commit_subjects"], list)


def test_detects_docs_tests_code_changes(tmp_path: Path) -> None:
    rp = tmp_path / "repo-d"
    _mk_git_repo(rp)
    (rp / "docs").mkdir(exist_ok=True)
    (rp / "docs" / "guide.md").write_text("docs\n", encoding="utf-8")
    (rp / "tests").mkdir(exist_ok=True)
    (rp / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (rp / "service.py").write_text("x=1\n", encoding="utf-8")
    out = repo_activity.collect_repo_activity(rp)
    assert out["docs_changed"] is True
    assert out["tests_changed"] is True
    assert out["code_changed"] is True
    assert out["activity_type"] in ("mixed", "code")


def test_builds_repo_activity_snapshot_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    rp = tmp_path / "repo-e"
    _mk_git_repo(rp)
    ingest_dir = tmp_path / "state" / "live_work_orchestration" / "ingestion"
    monkeypatch.setattr("brain.live_work_orchestration.ingestion.repo_activity._ingestion_dir", lambda: ingest_dir)
    snap = repo_activity.build_repo_activity_snapshot(
        {
            "repo_activity": {
                "enabled": True,
                "repo_roots": [str(tmp_path)],
                "scan_depth": 2,
                "include_file_samples": True,
                "max_file_samples": 5,
                "include_commit_subjects": True,
                "since_hours": 24,
            }
        }
    )
    assert snap["snapshot_type"] == "repo_activity_snapshot"
    assert (ingest_dir / "repo_activity_snapshot.json").is_file()


def test_integrates_into_daily_progress_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    ingest_dir = tmp_path / "ingestion"
    ingest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "snapshot_type": "repo_activity_snapshot",
        "generated_at": "2026-01-01T00:00:00Z",
        "freshness_seconds": 300,
        "stale": False,
        "confidence": 0.8,
        "source_files_or_tools": ["git"],
        "missing_sources": [],
        "data": {
            "activity": [
                {"repo_name": "x", "likely_feature_name": "feat/a", "changed_files_count": 2, "recent_commits_count": 1}
            ],
            "summary": {"repos_scanned": 1, "repos_with_activity": 1, "high_intensity_repos": 0},
            "progress_events": [
                {
                    "type": "repo_activity",
                    "repo_name": "x",
                    "feature_name": "feat/a",
                    "summary": "x activity",
                    "activity_type": "code",
                    "activity_intensity": "low",
                    "branch": "feat/a",
                    "evidence": ["git_status:2"],
                    "confidence": 0.8,
                    "observed_at": "2026-01-01T00:00:00Z",
                }
            ],
        },
        "summary_short": "s",
        "summary_detailed": "d",
        "evidence_items": [],
        "errors": [],
    }
    (ingest_dir / "repo_activity_snapshot.json").write_text(json.dumps(payload), encoding="utf-8")
    out = build_daily_progress_snapshot()
    data = out.get("data") or {}
    assert len(data.get("repo_activity_rows") or []) == 1
    assert len(data.get("repo_activity_events") or []) == 1


def test_existing_empty_repo_snapshot_not_marked_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    ingest_dir = tmp_path / "ingestion"
    ingest_dir.mkdir(parents=True, exist_ok=True)
    (ingest_dir / "repo_activity_snapshot.json").write_text(
        json.dumps(
            {
                "snapshot_type": "repo_activity_snapshot",
                "generated_at": "2026-01-01T00:00:00Z",
                "freshness_seconds": 300,
                "stale": False,
                "confidence": 0.5,
                "source_files_or_tools": ["git"],
                "missing_sources": [],
                "data": {"activity": [], "summary": {}, "progress_events": []},
                "summary_short": "empty",
                "summary_detailed": "empty",
                "evidence_items": [],
                "errors": [],
            }
        ),
        encoding="utf-8",
    )
    out = build_daily_progress_snapshot()
    assert "repo_activity_snapshot" not in (out.get("missing_sources") or [])


def test_no_full_file_read_in_collection() -> None:
    src = Path(repo_activity.__file__).read_text(encoding="utf-8")
    assert ".read_text(" not in src or "_parse_simple_yaml" in src
    assert "git status --short" in src or "status" in src


def test_handles_errors_gracefully() -> None:
    out = repo_activity.collect_repo_activity("Z:/does-not-exist-path")
    assert len(out.get("errors") or []) >= 1
    assert out.get("repo_path")


def test_populates_feature_ready_fields(tmp_path: Path) -> None:
    rp = tmp_path / "repo-f"
    _mk_git_repo(rp)
    out = repo_activity.collect_repo_activity(rp)
    for k in ("likely_feature_name", "linked_pr_guess", "feature_area", "rollout_stage", "activity_type", "activity_intensity"):
        assert k in out


def test_feature_name_normalizes_noisy_prefixes() -> None:
    out = repo_activity._normalize_feature_name("wip/my-feature", "fallback")
    assert out == "my-feature"
    out2 = repo_activity._normalize_feature_name("fix/bug-123", "fallback")
    assert out2 == "bug-123"


def test_commit_subjects_bounded_by_config(tmp_path: Path) -> None:
    rp = tmp_path / "repo-g"
    _mk_git_repo(rp)
    row = {
        "repo_activity": {
            "enabled": True,
            "repo_roots": [str(tmp_path)],
            "scan_depth": 2,
            "include_file_samples": True,
            "max_file_samples": 5,
            "include_commit_subjects": True,
            "max_commit_subjects": 1,
            "since_hours": 720,
        }
    }
    out = repo_activity.collect_all_repo_activity(row)
    items = out.get("activity_list") or []
    assert items
    assert len((items[0].get("recent_commit_subjects") or [])) <= 1
