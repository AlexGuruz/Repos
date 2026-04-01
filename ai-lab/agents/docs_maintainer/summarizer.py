"""
Docs summarizer: summarize docs_source/ or selected READMEs; write to summaries/.
"""
from __future__ import annotations

import json
from pathlib import Path


def summarize_docs(docs_root: Path, out_dir: Path) -> str:
    """Summarize markdown under docs_root; write summary to out_dir/docs_summary.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for p in docs_root.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:3000]
            summaries.append({"path": str(p.relative_to(docs_root)), "preview": text[:500]})
        except Exception:
            pass
    out_path = out_dir / "docs_summary.json"
    with open(out_path, "w") as f:
        json.dump({"source": str(docs_root), "files": summaries}, f, indent=2)
    return f"Wrote {out_path} ({len(summaries)} files)"
