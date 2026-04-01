import json
import asyncio
import os
from pathlib import Path
from fastapi import APIRouter
from core.config import settings
from core.ai_lab import AI_LAB_ROOT
from services.observability import log_api, log_error

router = APIRouter()


def _walk_repo(root: str, max_items: int = 400, max_depth: int = 4) -> list[dict]:
    result = []
    base = Path(root)
    if not base.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(base):
        # Prune recursion when we hit the depth cap.
        rel_from_base = os.path.relpath(dirpath, base)
        depth = 0 if rel_from_base == "." else len(Path(rel_from_base).parts)
        if depth >= max_depth:
            dirnames[:] = []
        if len(result) >= max_items:
            break
        dirnames[:] = [d for d in sorted(dirnames) if not d.startswith(".")]
        rel_dir = os.path.relpath(dirpath, base.parent).replace("\\", "/")
        result.append({"type": "dir", "path": rel_dir})
        if len(result) >= max_items:
            break
        for fname in sorted(filenames):
            if len(result) >= max_items:
                break
            fpath = os.path.join(dirpath, fname)
            try:
                stat = os.stat(fpath)
                size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                size, mtime = 0, 0
            result.append({
                "type": "file",
                "name": fname,
                "path": os.path.relpath(fpath, base.parent).replace("\\", "/"),
                "size_bytes": size,
                "mtime": mtime,
            })
    return result


@router.get("/api/repo/tree")
async def repo_tree():
    root = settings.ai_lab_governance_root or (str(AI_LAB_ROOT) if AI_LAB_ROOT.exists() else "")
    if not root:
        log_api("repo", "tree", configured=False, count=0)
        return {"tree": [], "note": "AI_LAB_GOVERNANCE_ROOT not set and ai-lab root not found"}
    # IMPORTANT: os.walk is synchronous and can block the event loop on large trees.
    # Run the walk in a thread so the API remains responsive.
    # Keep this low so the endpoint returns quickly even on large repos.
    max_items = 400
    max_depth = 4
    tree = await asyncio.to_thread(_walk_repo, root, max_items, max_depth)
    truncated = len(tree) >= max_items
    log_api("repo", "tree", configured=True, count=len(tree), truncated=truncated, root=root)
    return {
        "tree": tree,
        "note": (
            f"Tree truncated (max_items={max_items}, max_depth={max_depth}) for responsiveness."
            if truncated
            else ""
        ),
    }


@router.get("/api/repo/file")
async def repo_file(path: str):
    """Return basic metadata for a single file path."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        log_error("repo", "file_not_found", path=path)
        return {"error": "File not found"}
    stat = p.stat()
    log_api("repo", "file", path=str(p), size_bytes=stat.st_size)
    return {
        "path": str(p),
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


@router.get("/api/repo/summaries")
async def repo_summaries():
    """List repo scan summaries (cartographer output) for the Repo panel."""
    summaries_dir = AI_LAB_ROOT / "summaries" / "repos"
    if not summaries_dir.exists():
        log_api("repo", "summaries", count=0)
        return {"summaries": []}
    result = []
    for p in sorted(summaries_dir.glob("*.json")):
        try:
            with open(p) as f:
                data = json.load(f)
            result.append({
                "name": data.get("repo", p.stem),
                "path": data.get("path", ""),
                "entrypoints": data.get("entrypoints", []),
            })
        except (json.JSONDecodeError, OSError):
            result.append({"name": p.stem, "path": "", "entrypoints": []})
    log_api("repo", "summaries", count=len(result))
    return {"summaries": result}
