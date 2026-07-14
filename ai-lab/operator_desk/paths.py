"""Portable path discovery for Operator Desk. Never assume E:\\Repos only."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


@lru_cache(maxsize=1)
def operator_package_root() -> Path:
    return Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def ai_lab_root() -> Path:
    env = os.environ.get("AI_LAB_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if _is_dir(p):
            return p
    return operator_package_root().parent


def _candidate_monorepo_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("REPOS_ROOT", "AI_LAB_REPOS_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            roots.append(Path(raw).expanduser().resolve())
    lab = ai_lab_root()
    roots.append(lab.parent)
    for guess in (
        Path(r"E:\Repos"),
        Path(r"C:\Repos"),
        Path(r"C:\worker\repos"),
    ):
        roots.append(guess)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for r in roots:
        key = str(r).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


@lru_cache(maxsize=1)
def brain_vault_root() -> Path:
    for key in ("OPERATOR_BRAIN_VAULT_ROOT", "BRAIN_VAULT_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if _is_dir(p):
                return p
    lab = ai_lab_root()
    sibling = (lab.parent / "Ai" / "Obsidian" / "Brain").resolve()
    if _is_dir(sibling):
        return sibling
    for root in _candidate_monorepo_roots():
        candidate = (root / "Ai" / "Obsidian" / "Brain").resolve()
        if _is_dir(candidate):
            return candidate
    raise FileNotFoundError(
        "Brain vault not found. Set OPERATOR_BRAIN_VAULT_ROOT or BRAIN_VAULT_ROOT."
    )


def vault_index_path() -> Path:
    return brain_vault_root() / "VAULT-INDEX.md"


def active_priorities_path() -> Path:
    return brain_vault_root() / "Active Priorities.md"


def operator_jobs_dir() -> Path:
    return brain_vault_root() / "40_operator" / "jobs"


def operator_state_dir() -> Path:
    return ai_lab_root() / "state" / "operator"


def email_digest_cache_path() -> Path:
    return operator_state_dir() / "email_digest_cache.json"


def job_manifest_path() -> Path:
    return operator_package_root() / "config" / "job_manifest.yaml"


def operator_settings_path() -> Path:
    return operator_package_root() / "config" / "operator_settings.yaml"


def scripts_registry_path() -> Path:
    return ai_lab_root() / "registry" / "scripts.json"


def approval_pending_path() -> Path:
    return ai_lab_root() / "logs" / "approval_logs" / "pending.json"


def growflow_snapshot_path() -> Path:
    return ai_lab_root() / "state" / "prepared_context" / "growflow_snapshot.json"


def governance_root() -> Path | None:
    env = os.environ.get("AI_LAB_GOVERNANCE_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if _is_dir(p):
            return p
    sibling = (ai_lab_root().parent / "ai-lab-governance").resolve()
    if _is_dir(sibling):
        return sibling
    return None


def repo_registry_path() -> Path | None:
    gov = governance_root()
    if gov is None:
        return None
    p = gov / "registry" / "repo_registry.json"
    return p if _is_file(p) else None


def clear_path_caches() -> None:
    """Test helper — reset lru caches after env changes."""
    operator_package_root.cache_clear()
    ai_lab_root.cache_clear()
    brain_vault_root.cache_clear()
