"""
Repo search: search repos by keyword (filename + path), return ranked matches.
Used for "find it in repos", "search repos for X" (Phase-2).

Uses os.walk with directory pruning. The previous implementation used Path.rglob("*"),
which descended into .git, node_modules, venvs, etc. — easily 10+ minutes on a full
E:\\Repos tree on Windows.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

# ai-lab root
_ROOT = Path(__file__).resolve().parents[1]
# Repos root (E:\Repos or parent of ai-lab)
REPOS_ROOT = _ROOT.parent if _ROOT.name == "ai-lab" else Path("E:/Repos")

# Do not descend into these (huge or non-source trees).
# Descend into these dot-directories (tooling / editor); skip other hidden dirs.
_ALLOWED_DOT_DIRS = frozenset({".cursor", ".github", ".vscode", ".idea"})

_SKIP_DIR_NAMES = frozenset({
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".parcel-cache",
    "dist",
    "build",
    ".next",
    "target",
    "site-packages",
    "bower_components",
    "Pods",
    ".gradle",
    "coverage",
    "__MACOSX",
    ".svn",
    ".hg",
})

_ALLOWED_SUFFIXES = (".py", ".js", ".ts", ".json", ".md", ".yaml", ".yml", ".txt", ".sh")


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


def _prune_dirnames(dirnames: list[str]) -> None:
    """In-place prune for os.walk(topdown=True)."""
    i = 0
    while i < len(dirnames):
        d = dirnames[i]
        if d in _SKIP_DIR_NAMES:
            dirnames.pop(i)
            continue
        if d.startswith(".") and d not in _ALLOWED_DOT_DIRS:
            dirnames.pop(i)
            continue
        i += 1


def search_repos(query: str, repos_root: Path | None = None, max_results: int = 15) -> list[dict[str, Any]]:
    """
    Search under repos_root for files/dirs matching query (filename and path).
    Returns list of { path, score, why } sorted by score descending.
    """
    root = (repos_root or REPOS_ROOT).resolve()
    if not root.exists():
        return []
    query_lower = (query or "").strip().lower()
    if not query_lower:
        return []

    t0 = time.perf_counter()
    matches: list[tuple[float, Path, str]] = []
    files_scored = 0
    dirs_scored = 0

    try:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            _prune_dirnames(dirnames)
            dp = Path(dirpath)

            if dp.resolve() != root:
                if dp.name and not dp.name.startswith("."):
                    sc = _score_path(dp, query_lower)
                    if sc > 0:
                        dirs_scored += 1
                        matches.append((sc, dp, _why(dp, query_lower)))

            for fn in filenames:
                if not fn.endswith(_ALLOWED_SUFFIXES):
                    continue
                path = dp / fn
                sc = _score_path(path, query_lower)
                if sc > 0:
                    files_scored += 1
                    matches.append((sc, path, _why(path, query_lower)))
    except OSError:
        return []

    matches.sort(key=lambda x: (-x[0], str(x[1])))
    out = [
        {"path": str(m[1]), "score": round(m[0], 2), "why": m[2]}
        for m in matches[:max_results]
    ]

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    try:
        from brain.telemetry import log_event

        log_event(
            "repo_search_timing",
            query_preview=query_lower[:120],
            duration_ms=elapsed_ms,
            matches_returned=len(out),
            files_scored=files_scored,
            dirs_scored=dirs_scored,
            root=str(root),
        )
    except Exception:
        pass

    return out
