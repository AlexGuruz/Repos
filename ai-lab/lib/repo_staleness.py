"""Git last-commit age for configured repo roots (no network)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RepoPulse:
    path: str
    label: str
    last_commit_iso: str | None
    days_idle: float | None
    error: str | None = None


def _git_last_commit_date(repo: Path, pathspec: str | None = None) -> datetime | None:
    cmd = ["git", "-C", str(repo), "log", "-1", "--format=%cI"]
    if pathspec:
        cmd += ["--", pathspec]
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        return None
    line = (r.stdout or "").strip()
    if not line:
        return None
    # %cI is ISO8601
    return datetime.fromisoformat(line.replace("Z", "+00:00"))


def scan_repos(entries: list[dict], *, now: datetime | None = None) -> list[RepoPulse]:
    """
    entries: [{"path": "E:/Repos", "label": "AI-Lab", "git_path": "ai-lab"}, ...]
    Optional git_path scopes `git log` to that path under the repo root (monorepos).
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    out: list[RepoPulse] = []
    for e in entries:
        label = str(e.get("label") or e.get("path") or "?")
        raw = e.get("path")
        pathspec = (e.get("git_path") or e.get("pathspec") or "").strip() or None
        if not raw:
            out.append(RepoPulse(path="", label=label, last_commit_iso=None, days_idle=None, error="missing path"))
            continue
        p = Path(str(raw)).expanduser()
        if not p.is_dir():
            out.append(RepoPulse(path=str(p), label=label, last_commit_iso=None, days_idle=None, error="not a directory"))
            continue
        if not (p / ".git").exists():
            out.append(RepoPulse(path=str(p), label=label, last_commit_iso=None, days_idle=None, error="not a git repo"))
            continue
        try:
            dt = _git_last_commit_date(p, pathspec)
        except Exception as exc:
            out.append(RepoPulse(path=str(p), label=label, last_commit_iso=None, days_idle=None, error=str(exc)))
            continue
        if dt is None:
            out.append(RepoPulse(path=str(p), label=label, last_commit_iso=None, days_idle=None, error="git log failed"))
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt.astimezone(timezone.utc)
        days = delta.total_seconds() / 86400.0
        out.append(
            RepoPulse(
                path=str(p),
                label=label,
                last_commit_iso=dt.astimezone(timezone.utc).isoformat(),
                days_idle=round(days, 2),
                error=None,
            )
        )
    return out
