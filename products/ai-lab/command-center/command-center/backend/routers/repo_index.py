from __future__ import annotations

from fastapi import APIRouter, Query

from services.repo_index_coordinator import get_coordinator
from services.index_policy import get_expected_policy_identity
from services.supervisor_bridge import fetch_worker_repo_status

router = APIRouter()


@router.get("/api/repo/index_state")
async def repo_index_state(worker_repo_id: str | None = Query(None, description="If set, best-effort merge GET worker /repo_status?repo_id=...")):
    """
    Debug/status endpoint for the hub repo index coordinator.
    """
    expected = get_expected_policy_identity()
    out: dict = {
        "expected_identity": {
            "embedding_model_id": expected.embedding_model_id,
            "embedding_model_revision": expected.embedding_model_revision,
            "policy_hash": expected.policy_hash,
            "index_schema_version": expected.index_schema_version,
            "collection_layout_version": expected.collection_layout_version,
        },
        "repos": get_coordinator().get_state_snapshot(),
    }
    rid = (worker_repo_id or "").strip()
    if rid:
        w = await fetch_worker_repo_status(rid)
        if w is not None:
            out["worker_reported"] = w
        else:
            out["worker_reported"] = None
            out["worker_reported_error"] = "unavailable_or_tunnel_down"
    return out

