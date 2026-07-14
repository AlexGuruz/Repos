"""Shared fixtures for Operator Desk unit tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture()
def jobs_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    d = FIXTURES / "jobs"
    monkeypatch.setenv("OPERATOR_JOBS_DIR", str(d))
    from operator_desk.job_primer import clear_manifest_cache

    clear_manifest_cache()
    yield d
    clear_manifest_cache()


@pytest.fixture()
def tmp_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    snap = {
        "snapshot_type": "growflow_snapshot",
        "generated_at": "2099-01-01T00:00:00Z",
        "freshness_seconds": 3600,
        "source_files_or_tools": ["test"],
        "confidence": 0.9,
        "stale": False,
        "errors": [],
        "data": {
            "latest_sales_summary": {"gross": 123},
            "known_blockers": [],
        },
        "summary_short": "Test snapshot OK",
        "summary_detailed": "Detailed",
        "suggested_questions": [],
        "evidence_items": [],
    }
    path = tmp_path / "growflow_snapshot.json"
    path.write_text(json.dumps(snap), encoding="utf-8")

    import operator_desk.paths as pathmod

    monkeypatch.setattr(pathmod, "growflow_snapshot_path", lambda: path)
    return path
