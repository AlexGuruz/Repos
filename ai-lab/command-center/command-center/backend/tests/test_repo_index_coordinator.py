from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from services.index_job_types import BuildMetadata
from services.repo_index_coordinator import RepoIndexCoordinator


def _coordinator(tmp_path, monkeypatch) -> RepoIndexCoordinator:
    from core.config import settings

    monkeypatch.setattr(settings, "repo_index_state_path", str(tmp_path / "repo_index_state.json"))
    return RepoIndexCoordinator()


def _valid_meta(coord: RepoIndexCoordinator) -> BuildMetadata:
    ident = coord._expected_identity
    return BuildMetadata(
        repo_id="ai-lab",
        target="staging",
        build_id="build-1",
        staging_version="staging-v2",
        active_version_seen="active-v1",
        embedding_model_id_used=ident.embedding_model_id,
        embedding_model_revision_used=ident.embedding_model_revision,
        policy_hash_used=ident.policy_hash,
        index_schema_version_used=ident.index_schema_version,
        collection_layout_version_used=ident.collection_layout_version,
        metadata_readable=True,
        corruption_detected=False,
        files_considered=10,
        files_indexed=10,
        chunks_indexed=25,
        started_at=None,
        finished_at=None,
        warnings=[],
        errors=[],
        raw={},
    )


def test_validate_staging_build_requires_worker_smoke_ok(tmp_path, monkeypatch) -> None:
    coord = _coordinator(tmp_path, monkeypatch)
    coord._worker_retrieve = AsyncMock(return_value={"ok": True, "result": {}})  # type: ignore[method-assign]

    result = asyncio.run(coord._validate_staging_build("ai-lab", _valid_meta(coord)))

    assert result.ok is False
    assert result.severity == "gate_a"
    assert "smoke_test_worker_not_ok" in result.reasons


def test_promote_does_not_mutate_active_state_when_worker_rejects(tmp_path, monkeypatch) -> None:
    coord = _coordinator(tmp_path, monkeypatch)
    state = coord._get_state("ai-lab")
    state.active_version = "active-v1"
    state.dirty = True
    coord._worker_promote_repo_index = AsyncMock(  # type: ignore[method-assign]
        return_value={"ok": True, "result": {"ok": False, "error": "unknown staging_version"}}
    )

    with patch("services.repo_index_coordinator.bus.publish", new_callable=AsyncMock):
        asyncio.run(coord._promote("ai-lab", _valid_meta(coord)))

    assert coord._get_state("ai-lab").active_version == "active-v1"
    assert coord._get_state("ai-lab").dirty is True
    assert coord._get_state("ai-lab").last_error == "promote_failed:unknown staging_version"
