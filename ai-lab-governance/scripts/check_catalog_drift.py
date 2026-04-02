#!/usr/bin/env python3
"""
Run repo_shape evidence checks against main-rig paths in repo_registry.json.
Optionally emit updated inline evidence (stdout as YAML snippet) — v1 does not write registry/evidence/*.json.

Exit codes: 0 = all checked paths ok, 1 = drift detected, 2 = usage error

Environment:
  AI_LAB_GOVERNANCE_ROOT
  CATALOG_STRICT=1 — reserved for future stricter repo_shape policy
  CATALOG_SKIP_REPO_SHAPE=1 — skip all path checks (use on CI when repo_registry uses main-rig-only paths)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML required. pip install -r scripts/requirements-catalog.txt", file=sys.stderr)
    sys.exit(2)


def _root() -> Path:
    r = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if r:
        return Path(r)
    return Path(__file__).resolve().parent.parent


def _repo_paths(reg: dict[str, Any]) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for r in reg.get("repos") or []:
        if not isinstance(r, dict):
            continue
        rid = r.get("repo_id")
        p = r.get("path")
        if rid and p:
            out[str(rid)] = Path(p)
    return out


def _check_paths(repo_root: Path, rel_paths: list[str]) -> tuple[bool, str]:
    if not repo_root.is_dir():
        return False, f"repo root missing: {repo_root}"
    for rel in rel_paths:
        rel = rel.strip()
        if rel in (".", ""):
            continue
        target = (repo_root / rel).resolve()
        try:
            target.relative_to(repo_root.resolve())
        except ValueError:
            return False, f"path escapes repo: {rel}"
        if not target.exists():
            return False, f"missing path: {rel}"
    return True, "ok"


def main() -> int:
    root = _root()
    strict = os.environ.get("CATALOG_STRICT", "").strip() in ("1", "true", "yes")
    if os.environ.get("CATALOG_SKIP_REPO_SHAPE", "").strip() in ("1", "true", "yes"):
        print("OK: repo_shape checks skipped (CATALOG_SKIP_REPO_SHAPE=1)")
        return 0

    comp_path = root / "registry" / "components.yaml"
    reg_path = root / "registry" / "repo_registry.json"
    if not comp_path.is_file() or not reg_path.is_file():
        print("FAIL: components.yaml or repo_registry.json missing", file=sys.stderr)
        return 2

    with comp_path.open(encoding="utf-8") as f:
        comp_doc = yaml.safe_load(f)
    with reg_path.open(encoding="utf-8") as f:
        reg_doc = json.load(f)

    components = comp_doc.get("components") or []
    id_to_path = _repo_paths(reg_doc)
    failures: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for comp in components:
        if not isinstance(comp, dict):
            continue
        cid = comp.get("id", "?")
        evidence = comp.get("evidence") or {}
        for ev_key, ev in evidence.items():
            if not isinstance(ev, dict):
                continue
            if ev.get("type") != "repo_shape":
                continue
            spec = ev.get("spec") or {}
            rid = spec.get("repo_id")
            paths = spec.get("paths") or []
            if not rid:
                failures.append(f"{cid}/{ev_key}: spec.repo_id missing")
                continue
            base = id_to_path.get(str(rid))
            if not base:
                failures.append(f"{cid}/{ev_key}: unknown repo_id {rid!r}")
                continue
            ok, msg = _check_paths(base, [str(p) for p in paths])
            if not ok:
                failures.append(f"{cid}/{ev_key}: {msg}")

    if failures:
        print("DRIFT: repo_shape check failures:", file=sys.stderr)
        for f in failures:
            print(" ", f, file=sys.stderr)
        return 1

    print("OK: repo_shape drift check passed at", now)
    if strict:
        print("(strict mode: no optional probes failed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
