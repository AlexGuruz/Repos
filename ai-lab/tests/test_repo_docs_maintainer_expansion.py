from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from brain.orchestrator.main import run
from brain.repo_docs_repo_level import (
    assess_repo_documentation,
    build_repo_docs_workplan,
    check_repo_docs_consistency,
    create_repo_docs_batch_proposal,
)


def _minimal_valid_readme() -> str:
    return """# T

This is the overview paragraph with enough characters to count as substantive content here.

## Setup / installation

```bash
npm install
```

## Configuration / environment variables

Set `PORT` in the environment.

## Usage / entrypoints

```bash
npm start
```

## Architecture or system overview

Modular layout with docs and tests.

## Verification / how to confirm working

```bash
npm test
```

## Troubleshooting

See issues on the tracker.
"""


def test_repo_documentation_score_range_and_grade(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(_minimal_valid_readme(), encoding="utf-8")
    a = assess_repo_documentation(tmp_path, repo_id="t1")
    assert a["ok"] is True
    assert 0 <= a["score_0_to_100"] <= 100
    assert a["grade"] in ("A", "B", "C", "D", "F")


def test_missing_readme_lowers_score(tmp_path: Path) -> None:
    a = assess_repo_documentation(tmp_path, repo_id="x")
    assert a["score_0_to_100"] < 50
    assert "README.md" in (a.get("missing_docs") or [])


def test_invalid_readme_lowers_score_and_reports_sections(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Only title\n", encoding="utf-8")
    a = assess_repo_documentation(tmp_path)
    assert a["score_0_to_100"] < 80
    assert a.get("invalid_docs") or a.get("weak_sections")


def test_workplan_groups_multiple_doc_tasks(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# bad\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "runbook_incident_runbook.md").write_text(
        "## Purpose\n\n" + ("p" * 50) + "\n## Steps\n\n```bash\necho x\n```\n"
        "## Expected result\n\n" + ("e" * 50) + "\n## Failure handling\n\n" + ("f" * 50),
        encoding="utf-8",
    )
    wp = build_repo_docs_workplan(tmp_path)
    assert wp.get("ok") is True
    assert len(wp.get("ordered_tasks") or []) >= 1


def test_consistency_checker_missing_referenced_file(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        _minimal_valid_readme() + "\nSee [missing](./NONEXISTENT_DOC_LINK.md).\n",
        encoding="utf-8",
    )
    c = check_repo_docs_consistency(tmp_path)
    types = {i.get("type") for i in (c.get("issues") or [])}
    assert "missing_link_target" in types


def test_batch_proposal_approval_required_no_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "README.md").write_text(_minimal_valid_readme(), encoding="utf-8")
    before = (tmp_path / "README.md").read_text(encoding="utf-8")
    prop = create_repo_docs_batch_proposal(tmp_path)
    assert prop.get("approval_required") is True
    assert prop.get("no_direct_write_performed") is True
    assert (tmp_path / "README.md").read_text(encoding="utf-8") == before


def test_batch_proposal_risk_increases_with_many_files(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    d = tmp_path / "docs"
    d.mkdir()
    for i in range(6):
        (d / f"x{i}.md").write_text(f"broken [l](./missing{i}.md)\n", encoding="utf-8")
    wp = build_repo_docs_workplan(tmp_path)
    prop = create_repo_docs_batch_proposal(tmp_path)
    assert prop.get("risk_level") in ("high", "medium")


def test_no_worker_for_scoring_workplan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("worker must not be called")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    (tmp_path / "README.md").write_text(_minimal_valid_readme(), encoding="utf-8")
    assess_repo_documentation(tmp_path)
    build_repo_docs_workplan(tmp_path)


def test_orchestrator_score_route_no_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("worker must not be called")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    (tmp_path / "README.md").write_text(_minimal_valid_readme(), encoding="utf-8")
    out = run(
        f"score repo documentation — {tmp_path}",
        llm_base_url="",
        llm_model="",
        session_id=f"rd8-{uuid.uuid4().hex[:6]}",
    )
    assert "repo_documentation_score" in out["reply"]
