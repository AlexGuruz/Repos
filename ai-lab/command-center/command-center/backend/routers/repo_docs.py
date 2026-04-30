"""
Read-only repo documentation maintainer API (Phase 8).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Query

router = APIRouter()

# ai-lab repo root: .../backend/routers -> parents[3] == ai-lab
_DEFAULT_DOC_ROOT = Path(__file__).resolve().parents[3]


def _repo_docs_status_sync() -> dict:
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.repo_docs_maintainer import analyze_repo_docs_status

    s = analyze_repo_docs_status()
    return {
        "ok": bool(s.get("ok")),
        "generated_at": s.get("generated_at"),
        "stale": s.get("stale"),
        "confidence": s.get("confidence"),
        "findings_count": len(s.get("findings") or []),
        "readme_validations_count": len(s.get("readme_validations") or []),
        "limited": bool(s.get("limited")),
        "missing_data": s.get("missing_data") or [],
    }


def _repo_docs_score_sync(repo: str) -> dict:
    from core.ai_lab import ensure_ai_lab_root_on_path

    ensure_ai_lab_root_on_path()
    from brain.repo_docs_repo_level import assess_repo_documentation, resolve_repo_docs_target

    msg = f"score repo documentation for {repo}" if repo else "score repo documentation"
    path, rid, err = resolve_repo_docs_target(msg, default_root=_DEFAULT_DOC_ROOT)
    if path is None or not path.is_dir():
        return {"ok": False, "error": err or "invalid_repo_path", "repo_query": repo}
    out = assess_repo_documentation(path, repo_id=rid or repo)
    out.pop("_score_breakdown", None)
    return out


@router.get("/api/repo-docs/status")
async def repo_docs_status():
    return await asyncio.to_thread(_repo_docs_status_sync)


@router.get("/api/repo-docs/score")
async def repo_docs_score(repo: str = Query("ai-lab", description="Repo name (repo_pulse) or use ai-lab")):
    return await asyncio.to_thread(_repo_docs_score_sync, repo)
