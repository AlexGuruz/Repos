"""
Repo search: search repos by keyword (filename + path), return ranked matches.
Used for "find it in repos", "search repos for X" (Phase-2).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# ai-lab root
_ROOT = Path(__file__).resolve().parents[1]
# Repos root (E:\Repos or parent of ai-lab)
REPOS_ROOT = _ROOT.parent if _ROOT.name == "ai-lab" else Path("E:/Repos")


def _score_path(path: Path, query_lower: str) -> float:
    """Score 0..1 by filename and path segments matching query."""
    score = 0.0
    parts = query_lower.split()
    path_str = path.as_posix().lower()
    name = path.name.lower()
    for p in parts:
        if len(p) < 2:
            continue
        if p in name:
            score += 0.5
        if p in path_str:
            score += 0.2
    if score > 1.0:
        score = 1.0
    return score


def _why(path: Path, query_lower: str) -> str:
    """Short reason for match."""
    name = path.name.lower()
    parts = query_lower.split()
    for p in parts:
        if p in name:
            return "filename match"
    return "path match"


def search_repos(query: str, repos_root: Path | None = None, max_results: int = 15) -> list[dict[str, Any]]:
    """
    Search under repos_root for files/dirs matching query (filename and path).
    Returns list of { path, score, why } sorted by score descending.
    """
    root = repos_root or REPOS_ROOT
    if not root.exists():
        return []
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return []
    matches: list[tuple[float, Path, str]] = []
    try:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".js", ".ts", ".json", ".md", ".yaml", ".yml", ".txt", ".sh"):
                sc = _score_path(path, query_lower)
                if sc > 0:
                    why = _why(path, query_lower)
                    matches.append((sc, path, why))
            elif path.is_dir() and not path.name.startswith(".") and path.name != "node_modules" and path.name != "__pycache__":
                sc = _score_path(path, query_lower)
                if sc > 0:
                    why = _why(path, query_lower)
                    matches.append((sc, path, why))
    except OSError:
        return []
    matches.sort(key=lambda x: (-x[0], str(x[1])))
    return [
        {"path": str(m[1]), "score": round(m[0], 2), "why": m[2]}
        for m in matches[:max_results]
    ]
