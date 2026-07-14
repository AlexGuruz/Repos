"""Repo awareness from governance catalog / registry — bounded, no tree walk."""
from __future__ import annotations

import json
from typing import Any

from .. import paths as pathmod
from ..errors import DEPENDENCY_UNAVAILABLE, REPO_REGISTRY_INVALID
from ..models import RepoMapEntry, RepoMapResult


def get_repo_map_summary(query: str | None = None) -> RepoMapResult:
    reg_path = pathmod.repo_registry_path()
    if reg_path is None:
        # Fallback: ai-lab ops registry systems.yaml is not JSON; try empty with warning
        return RepoMapResult(
            ok=False,
            source="repo_registry",
            freshness="unavailable",
            error_code=DEPENDENCY_UNAVAILABLE,
            degraded=True,
            query=query,
            warnings=["ai-lab-governance repo_registry.json not found"],
        )
    try:
        raw = json.loads(reg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RepoMapResult(
            ok=False,
            source="repo_registry",
            freshness="unavailable",
            error_code=REPO_REGISTRY_INVALID,
            degraded=True,
            query=query,
            warnings=[str(exc)],
        )

    repos_raw: list[Any]
    if isinstance(raw, dict):
        if isinstance(raw.get("repos"), list):
            repos_raw = raw["repos"]
        else:
            # map form {id: {...}}
            repos_raw = []
            for rid, meta in raw.items():
                if rid in ("version", "notes"):
                    continue
                if isinstance(meta, dict):
                    row = dict(meta)
                    row.setdefault("id", rid)
                    row.setdefault("repo_id", rid)
                    repos_raw.append(row)
                else:
                    repos_raw.append({"repo_id": rid, "path": str(meta), "summary": ""})
    elif isinstance(raw, list):
        repos_raw = raw
    else:
        return RepoMapResult(
            ok=False,
            source="repo_registry",
            freshness="unavailable",
            error_code=REPO_REGISTRY_INVALID,
            degraded=True,
            query=query,
            warnings=["Unexpected registry shape"],
        )

    q = (query or "").strip().lower()
    entries: list[RepoMapEntry] = []
    for row in repos_raw:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("repo_id") or row.get("id") or row.get("name") or "")
        path = str(row.get("path") or row.get("root") or row.get("repo_path") or "")
        summary = str(row.get("summary") or row.get("description") or row.get("purpose") or "")[:240]
        if not rid and not path:
            continue
        blob = f"{rid} {path} {summary}".lower()
        if q and q not in blob:
            continue
        entries.append(RepoMapEntry(repo_id=rid or path, path=path, summary=summary))
        if len(entries) >= 50:
            break

    return RepoMapResult(
        ok=True,
        source="repo_registry",
        freshness="fresh",
        repos=entries,
        query=query,
        warnings=["Truncated to 50 repos"] if len(entries) >= 50 else [],
    )
