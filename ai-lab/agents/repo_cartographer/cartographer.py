"""
Repo cartographer: scan repo root, produce file-tree and module summaries; write to summaries/repos/.
V1: also produces markdown summary and top_findings for structured tool result.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


def _tree(path: Path, prefix: str = "", max_depth: int = 4, depth: int = 0) -> list[str]:
    if depth >= max_depth:
        return []
    lines = []
    try:
        children = sorted(path.iterdir())
    except OSError:
        return []
    dirs = [c for c in children if c.is_dir() and not c.name.startswith(".")]
    files = [c for c in children if c.is_file()]
    for d in dirs[:20]:
        lines.append(f"{prefix}{d.name}/")
        lines.extend(_tree(d, prefix + "  ", max_depth, depth + 1))
    for f in files[:30]:
        lines.append(f"{prefix}{f.name}")
    if len(dirs) > 20 or len(files) > 30:
        lines.append(f"{prefix}...")
    return lines


def run_scan_to_dict(repo_root: Path, name: str | None = None) -> dict | None:
    """
    Scan repo_root and return summary dict (no disk write). Used by worker so main can persist.
    Returns None if path does not exist.
    """
    if not repo_root.exists():
        return None
    name = name or repo_root.name
    tree_lines = _tree(repo_root)
    readme = None
    for f in ("README.md", "Readme.md", "README.rst"):
        p = repo_root / f
        if p.exists():
            readme = p.read_text(encoding="utf-8", errors="replace")[:2000]
            break
    summary = {
        "repo": name,
        "path": str(repo_root),
        "file_tree_sample": tree_lines,
        "readme_preview": readme,
        "entrypoints": [],
    }
    for entry in ("main.py", "app.py", "index.js", "package.json"):
        p = repo_root / entry
        if p.exists():
            summary["entrypoints"].append(entry)
    return summary


def _top_findings(summary: dict, repo_root: Path) -> list[str]:
    """Derive human-readable findings from scan summary."""
    findings = []
    if not summary.get("readme_preview"):
        findings.append(f"Repo {summary.get('repo', '')} has no README or equivalent")
    if not summary.get("entrypoints"):
        findings.append(f"No common entrypoints (main.py, app.py, package.json) in {summary.get('repo', '')}")
    if summary.get("file_tree_sample"):
        tree = " ".join(summary["file_tree_sample"])
        if "requirements.txt" in tree and "requirements" in tree and "lock" not in tree.lower():
            findings.append("Has requirements.txt but no obvious lock file")
    return findings[:10]


def _summary_to_markdown(summary: dict, top_findings: list[str], generated_at: str) -> str:
    """Produce human-readable markdown summary."""
    repo = summary.get("repo", "unknown")
    path = summary.get("path", "")
    lines = [
        "# Repo Scan Summary",
        "",
        f"**Scanned:** {repo}",
        f"**Path:** {path}",
        f"**Generated:** {generated_at}",
        "",
        "## Top Findings",
        "",
    ]
    for f in top_findings:
        lines.append(f"- {f}")
    if not top_findings:
        lines.append("- No notable issues detected from structure.")
    lines.extend(["", "## Entrypoints", ""])
    for ep in summary.get("entrypoints") or []:
        lines.append(f"- {ep}")
    if not summary.get("entrypoints"):
        lines.append("- None found.")
    lines.extend(["", "## File tree (sample)", ""])
    for line in (summary.get("file_tree_sample") or [])[:30]:
        lines.append(f"    {line}")
    return "\n".join(lines)


def run_scan(repo_root: Path, name: str | None = None) -> str:
    """
    Scan repo_root, write summary to summaries/repos/<name>.json. Return short status.
    """
    name = name or repo_root.name
    summary = run_scan_to_dict(repo_root, name)
    if summary is None:
        return f"Path does not exist: {repo_root}"
    ai_lab = Path(__file__).resolve().parents[2]
    out_dir = ai_lab / "summaries" / "repos"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    return f"Wrote {out_path}"


def run_scan_structured(repo_root: Path, name: str | None = None) -> dict | None:
    """
    Scan repo_root, write JSON + markdown summary, return structured result for V1 tool contract.
    Returns None if path does not exist. Otherwise returns:
      status, tool, timestamp, artifacts: [{type, path}], summary: {repos_scanned, top_findings}, stdout_excerpt
    """
    name = name or repo_root.name
    summary = run_scan_to_dict(repo_root, name)
    if summary is None:
        return None
    ai_lab = Path(__file__).resolve().parents[2]
    out_dir = ai_lab / "summaries" / "repos"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    top_findings = _top_findings(summary, repo_root)
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    md_path = out_dir / f"{name}_summary.md"
    md_content = _summary_to_markdown(summary, top_findings, generated_at)
    md_path.write_text(md_content, encoding="utf-8")
    return {
        "status": "ok",
        "tool": "repo_scan",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "artifacts": [
            {"type": "json", "path": str(out_path)},
            {"type": "markdown", "path": str(md_path)},
        ],
        "summary": {
            "repos_scanned": 1,
            "repo_name": name,
            "top_findings": top_findings,
        },
        "stdout_excerpt": f"Repo scan done. Wrote {out_path}",
    }
