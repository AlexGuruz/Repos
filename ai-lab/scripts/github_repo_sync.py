#!/usr/bin/env python3
"""Keep local git repos aligned with GitHub (fetch, optional pull --rebase, optional push).

Default is dry-run: prints status only. Use --apply with --pull and/or --push to change remotes.

Config: state/github_repo_sync_config.json next to ai-lab (repo-relative paths under workspace_root).
Override config path with --config. Override workspace with --workspace-root.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RepoStatus:
    label: str
    path: Path
    branch_line: str
    dirty: bool
    ahead: int
    behind: int
    has_upstream: bool
    error: str | None = None


def _ai_lab_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_config(path: Path | None) -> dict[str, Any]:
    cfg_path = path or (_ai_lab_root() / "state" / "github_repo_sync_config.json")
    if not cfg_path.is_file():
        raise SystemExit(f"missing config: {cfg_path}")
    return json.loads(cfg_path.read_text(encoding="utf-8"))


def _run(
    cwd: Path,
    *args: str,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _parse_branch_status(line: str) -> tuple[bool, int, int]:
    """Parse first line of git status -sb. Returns (has_upstream, ahead, behind)."""
    if not line.startswith("## "):
        return False, 0, 0
    rest = line[3:].strip()
    if "..." not in rest:
        return False, 0, 0
    # e.g. main...origin/main or cursor/foo...origin/cursor/foo [ahead 1, behind 2]
    head, remote_part = rest.split("...", 1)
    _ = head  # branch name unused
    m_brackets = re.search(r"\[([^\]]+)\]", remote_part)
    if not m_brackets:
        return True, 0, 0
    ahead = behind = 0
    inner = m_brackets.group(1)
    for part in inner.split(","):
        part = part.strip()
        ma = re.match(r"ahead (\d+)", part)
        mb = re.match(r"behind (\d+)", part)
        if ma:
            ahead = int(ma.group(1))
        if mb:
            behind = int(mb.group(1))
    return True, ahead, behind


def _is_dirty(porcelain: str) -> bool:
    for line in porcelain.splitlines():
        if not line:
            continue
        # ignore ignored untracked if we only care about tracked — any porcelain line means dirty enough
        return True
    return False


def inspect_repo(repo_dir: Path, label: str) -> RepoStatus:
    if not (repo_dir / ".git").exists():
        return RepoStatus(
            label=label,
            path=repo_dir,
            branch_line="(not a git repo)",
            dirty=False,
            ahead=0,
            behind=0,
            has_upstream=False,
            error="missing .git",
        )
    st = _run(repo_dir, "status", "-sb", "--porcelain")
    if st.returncode != 0:
        return RepoStatus(
            label=label,
            path=repo_dir,
            branch_line="",
            dirty=False,
            ahead=0,
            behind=0,
            has_upstream=False,
            error=(st.stderr or st.stdout or "").strip() or "git status failed",
        )
    porcelain_lines = [ln for ln in st.stdout.splitlines() if ln and not ln.startswith("## ")]
    dirty = bool(porcelain_lines)
    br = _run(repo_dir, "status", "-sb")
    first = br.stdout.splitlines()[0] if br.stdout else "##"
    has_upstream, ahead, behind = _parse_branch_status(first)
    return RepoStatus(
        label=label,
        path=repo_dir,
        branch_line=first,
        dirty=dirty,
        ahead=ahead,
        behind=behind,
        has_upstream=has_upstream,
        error=None,
    )


def _fetch(repo_dir: Path, remote: str) -> str | None:
    p = _run(repo_dir, "fetch", remote, timeout=300)
    if p.returncode != 0:
        return (p.stderr or p.stdout or "").strip() or "fetch failed"
    return None


def _pull_rebase(repo_dir: Path) -> str | None:
    # Uses branch.<name>.merge remote-tracking branch
    p = _run(repo_dir, "pull", "--rebase", timeout=300)
    if p.returncode != 0:
        return (p.stderr or p.stdout or "").strip() or "pull --rebase failed"
    return None


def _push(repo_dir: Path) -> str | None:
    p = _run(repo_dir, "push", timeout=300)
    if p.returncode != 0:
        return (p.stderr or p.stdout or "").strip() or "push failed"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--config",
        type=Path,
        default=None,
        help="JSON config path (default: ai-lab/state/github_repo_sync_config.json)",
    )
    ap.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Override workspace_root from config",
    )
    ap.add_argument("--fetch", action="store_true", help="git fetch <remote> for each repo")
    ap.add_argument("--pull", action="store_true", help="git pull --rebase when behind (needs --apply)")
    ap.add_argument("--push", action="store_true", help="git push when ahead and clean (needs --apply)")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually run pull/push/fetch (without this, only prints a plan; fetch still runs if --fetch)",
    )
    ap.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write machine-readable summary JSON to this path",
    )
    args = ap.parse_args()

    cfg = _load_config(args.config)
    root = Path(args.workspace_root or cfg["workspace_root"]).resolve()
    remote = str(cfg.get("remote") or "origin")
    entries = cfg.get("repos") or []
    if not entries:
        print("config.repos is empty", file=sys.stderr)
        return 1

    results: list[dict[str, Any]] = []
    exit_code = 0

    for entry in entries:
        rel = entry["path"]
        label = entry.get("label") or rel
        repo_fetch = entry.get("fetch", True)
        repo_dir = (root / rel).resolve()
        status = inspect_repo(repo_dir, label)
        row: dict[str, Any] = {
            "label": label,
            "path": str(repo_dir),
            "branch_line": status.branch_line,
            "dirty": status.dirty,
            "ahead": status.ahead,
            "behind": status.behind,
            "has_upstream": status.has_upstream,
            "error": status.error,
        }
        print(f"\n=== {label} ===")
        print(status.branch_line)
        if status.error:
            print(f"  skip: {status.error}")
            results.append(row)
            exit_code = 1
            continue
        if status.dirty:
            print("  working tree: DIRTY (not pushing)")
            row["would_push"] = False
            row["would_pull"] = status.behind > 0
        else:
            row["would_push"] = status.ahead > 0 and status.has_upstream
            row["would_pull"] = status.behind > 0 and status.has_upstream

        if args.fetch:
            if not repo_fetch:
                print(f"  git fetch {remote} … skipped (config fetch=false for this repo)")
                row["fetch_skipped"] = True
            else:
                print(f"  git fetch {remote} …")
                err = _fetch(repo_dir, remote)
                if err:
                    print(f"  fetch error: {err}")
                    row["fetch_error"] = err
                    exit_code = 1
                else:
                    row["fetch_error"] = None
                row["fetch_skipped"] = False
                status = inspect_repo(repo_dir, label)
                row["ahead"] = status.ahead
                row["behind"] = status.behind
                row["branch_line"] = status.branch_line
                row["dirty"] = status.dirty
                row["has_upstream"] = status.has_upstream
                print(f"  after fetch: {status.branch_line}")
                if status.dirty:
                    row["would_push"] = False
                else:
                    row["would_push"] = status.ahead > 0 and status.has_upstream
                row["would_pull"] = status.behind > 0 and status.has_upstream

        if args.pull:
            if not status.has_upstream:
                print("  pull skipped: no upstream tracking branch")
            elif status.behind > 0:
                if args.apply:
                    print("  git pull --rebase …")
                    err = _pull_rebase(repo_dir)
                    if err:
                        print(f"  pull error: {err}")
                        row["pull_error"] = err
                        exit_code = 1
                    else:
                        row["pull_error"] = None
                        status = inspect_repo(repo_dir, label)
                        row["branch_line"] = status.branch_line
                        row["ahead"] = status.ahead
                        row["behind"] = status.behind
                else:
                    print(f"  dry-run: would pull --rebase ({status.behind} behind)")
            else:
                print("  pull: not behind")

        if args.push:
            if status.dirty:
                print("  push skipped: dirty working tree")
            elif not status.has_upstream:
                print("  push skipped: no upstream (set with git push -u)")
            elif status.ahead > 0:
                if args.apply:
                    print("  git push …")
                    err = _push(repo_dir)
                    if err:
                        print(f"  push error: {err}")
                        row["push_error"] = err
                        exit_code = 1
                    else:
                        row["push_error"] = None
                else:
                    print(f"  dry-run: would push ({status.ahead} ahead)")
            else:
                print("  push: not ahead")

        results.append(row)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"repos": results}, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")

    if not args.apply and (args.pull or args.push):
        print("\nNote: --pull/--push were dry-run only; add --apply to execute.", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
