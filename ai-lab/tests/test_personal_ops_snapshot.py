from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from brain.prepared_context.builders import build_personal_ops_snapshot
from brain.prepared_context.store import write_snapshot


@pytest.fixture
def minimal_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-m", "init"], check=True, capture_output=True)
    return tmp_path


def test_personal_ops_snapshot_has_meaningful_evidence_when_config_and_git_exist(
    monkeypatch: pytest.MonkeyPatch, minimal_git_repo: Path,
) -> None:
    cfg = minimal_git_repo / "personal_ops.yaml"
    root = str(minimal_git_repo).replace("\\", "/")
    cfg.write_text(
        f"stale_warning_days: 999\nrepos:\n  - path: {root}\n    label: TestRepo\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "brain.prepared_context.builders._personal_ops_config_files",
        lambda: [cfg],
    )
    snap = build_personal_ops_snapshot()
    assert snap.data.get("repo_pulse"), "expected repo_pulse rows from scan_repos"
    assert any(e.get("title") == "Repo pulse (git idle)" for e in snap.evidence_items)
    assert len(snap.evidence_items) >= 2
    ms = snap.data.get("missing_sources") or []
    assert isinstance(ms, list)
    allowed = {"calendar_not_configured", "no_project_agenda_snapshot", "no_recent_alerts"}
    assert set(ms) <= allowed


def test_personal_ops_snapshot_merges_cached_project_agenda(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from brain.prepared_context import builders

    cfg = tmp_path / "empty.yaml"
    cfg.write_text("repos: []\n", encoding="utf-8")
    monkeypatch.setattr("brain.prepared_context.builders._personal_ops_config_files", lambda: [cfg])

    def _fake_agenda(_name: str):
        if _name == "project_agenda":
            return {
                "snapshot_type": "project_agenda",
                "generated_at": "2026-01-01T00:00:00Z",
                "data": {
                    "today_focus": ["A"],
                    "blocked_items": ["B: blocked"],
                    "next_actions": ["Do X"],
                },
            }
        return None

    monkeypatch.setattr(builders, "load_snapshot", _fake_agenda)
    snap = build_personal_ops_snapshot()
    assert snap.data.get("project_focus", {}).get("today_focus") == ["A"]
    assert snap.data.get("project_schedule")
    assert any("Project agenda (cached)" in (e.get("title") or "") for e in snap.evidence_items)


def test_loader_selects_personal_ops_for_focus_question(monkeypatch: pytest.MonkeyPatch) -> None:
    from brain.prepared_context.builders import build_personal_ops_snapshot
    from brain.prepared_context.loader import try_prepared_context_answer

    monkeypatch.setattr(
        "brain.prepared_context.builders._personal_ops_config_files",
        lambda: [],
    )
    write_snapshot(build_personal_ops_snapshot())
    out = try_prepared_context_answer("what should i focus on today?", "answer")
    assert out is not None
    assert "personal_ops_snapshot" in out["reply"]
