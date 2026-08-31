#!/usr/bin/env python3
"""Lean context catalog: git-tracked files only.

Inspired by Sourcegraph Zoekt / ctags: never walk untracked trees, never
follow symlinks across an exfat disk. Cursor's rg --files --follow on
/mnt/workshop is what pins this machine.

Usage:
  python3 lean_index.py build
  python3 lean_index.py search PATTERN
  python3 lean_index.py stats
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPOS_ROOT = Path("/mnt/workshop/Repos")
CACHE = Path.home() / ".cache" / "acheron-lean-index"
DB = CACHE / "index.sqlite"
MANIFEST = CACHE / "manifest.json"

SCAN_ROOTS = [
    REPOS_ROOT / "products",
    REPOS_ROOT / "internal",
    REPOS_ROOT / "tools" / "migration",
]

SKIP_DIR_NAMES = {
    "node_modules",
    "__pycache__",
    ".venv",
    "winpython",
    "archive",
    "worktrees",
}


def scan_targets(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if (root / ".git").exists() or root.name == "migration":
        return [root]
    try:
        children = list(root.iterdir())
    except OSError:
        return []
    found: list[Path] = []
    for child in children:
        if not child.is_dir() or child.name in SKIP_DIR_NAMES or child.name.startswith("."):
            continue
        if (child / ".git").exists():
            found.append(child)
            continue
        try:
            grandchildren = list(child.iterdir())
        except OSError:
            continue
        found.extend(
            g
            for g in grandchildren
            if g.is_dir() and (g / ".git").exists() and g.name not in SKIP_DIR_NAMES
        )
    return found


def files_for(repo: Path) -> tuple[list[str], str]:
    if (repo / ".git").exists():
        return ls_files(repo), "git"
    return [], "skip-no-git"


def ls_files(repo: Path) -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "--cached"],
        capture_output=True,
        check=False,
    )
    if r.returncode != 0:
        return []
    return [p.decode("utf-8", "surrogateescape") for p in r.stdout.split(b"\0") if p]


def build() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.execute(
        "CREATE TABLE files (repo TEXT NOT NULL, relpath TEXT NOT NULL, PRIMARY KEY (repo, relpath))"
    )
    conn.execute("CREATE VIRTUAL TABLE files_fts USING fts5(repo, relpath)")
    repos_meta = []
    total = 0
    for root in SCAN_ROOTS:
        for repo in scan_targets(root):
            rel_repo = str(repo.relative_to(REPOS_ROOT))
            paths, method = files_for(repo)
            if method == "skip-no-git":
                print(f"{rel_repo}: skipped (no .git; open this folder directly in Cursor)")
                continue
            rows = [(rel_repo, p) for p in paths if p]
            conn.executemany("INSERT OR IGNORE INTO files(repo, relpath) VALUES (?, ?)", rows)
            conn.executemany(
                "INSERT INTO files_fts(repo, relpath) VALUES (?, ?)", rows
            )
            total += len(rows)
            repos_meta.append({"repo": rel_repo, "files": len(rows), "method": method})
            print(f"{rel_repo}: {len(rows)} files ({method})")
    conn.commit()
    conn.close()
    MANIFEST.write_text(
        json.dumps(
            {
                "built_at": datetime.now(timezone.utc).isoformat(),
                "method": "git ls-files --cached only (no untracked, no --follow)",
                "file_count": total,
                "repos": repos_meta,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"indexed {total} files -> {DB}")


def search(pattern: str, limit: int = 50) -> None:
    if not DB.exists():
        print("no index; run: python3 lean_index.py build", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = pattern.replace('"', '""')
    rows = conn.execute(
        "SELECT repo, relpath FROM files_fts WHERE files_fts MATCH ? LIMIT ?",
        (q, limit),
    ).fetchall()
    conn.close()
    for repo, relpath in rows:
        print(f"{repo}/{relpath}")


def stats() -> None:
    if MANIFEST.exists():
        print(MANIFEST.read_text())
        return
    print("no index; run: python3 lean_index.py build", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "build":
        build()
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("usage: lean_index.py search PATTERN", file=sys.stderr)
            sys.exit(2)
        search(" ".join(sys.argv[2:]))
    elif cmd == "stats":
        stats()
    else:
        print("usage: lean_index.py [build|search PATTERN|stats]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
