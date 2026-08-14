"""Senior layout path SSOT with dual-read (legacy flat + products/ zones).

Usage:
  from repos_paths import repos_root, product, vault_root, ai_lab_root

Env overrides:
  REPOS_ROOT, AI_LAB_REPOS_ROOT, AI_LAB_ROOT, AI_LAB_GOVERNANCE_ROOT,
  OPERATOR_BRAIN_VAULT_ROOT, BRAIN_VAULT_ROOT
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LAYOUT_PATH = _HERE.parent / "layout.json"


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
def load_layout() -> dict[str, Any]:
    if not _is_file(_LAYOUT_PATH):
        return {"moves": [], "vault": {}, "products_dir": "products"}
    return json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))


def clear_caches() -> None:
    load_layout.cache_clear()
    repos_root.cache_clear()
    products_root.cache_clear()
    ai_lab_root.cache_clear()
    vault_root.cache_clear()
    governance_root.cache_clear()


@lru_cache(maxsize=1)
def repos_root() -> Path:
    for key in ("REPOS_ROOT", "AI_LAB_REPOS_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if _is_dir(p):
                return p

    # Walk up from this file looking for markers
    layout = load_layout()
    markers = set(layout.get("repos_root_markers") or ["docs", "tools"])
    for parent in [_HERE, *_HERE.parents]:
        if any(_is_dir(parent / m) for m in markers) and (
            _is_dir(parent / "products")
            or _is_dir(parent / "Project-Kylo")
            or _is_dir(parent / "ai-lab")
            or _is_file(parent / "README.md")
        ):
            # Prefer directory that contains layout or classic flagships
            if _is_dir(parent / "tools" / "migration") or _is_dir(parent / "Project-Kylo") or _is_dir(parent / "products"):
                return parent.resolve()

    for guess in (Path(r"E:\Repos"), Path(r"C:\Repos"), Path(r"C:\worker\repos")):
        if _is_dir(guess):
            return guess.resolve()

    raise FileNotFoundError("REPOS_ROOT not found. Set REPOS_ROOT to the monorepo root.")


@lru_cache(maxsize=1)
def products_root() -> Path:
    root = repos_root()
    products = root / "products"
    if _is_dir(products):
        return products.resolve()
    return root  # pre-migrate: products live at monorepo root


def _move_by_id(product_id: str) -> dict[str, Any] | None:
    for m in load_layout().get("moves") or []:
        if m.get("id") == product_id:
            return m
    return None


def product(product_id: str) -> Path:
    """Resolve a product/internal id with dual-read (new path then legacy from)."""
    root = repos_root()
    move = _move_by_id(product_id)
    if move:
        new_path = root / move["to"].replace("/", os.sep)
        if _is_dir(new_path):
            return new_path.resolve()
        legacy = root / move["from"]
        if _is_dir(legacy):
            return legacy.resolve()
        return new_path.resolve()  # preferred target even if missing (callers check)

    # Common aliases
    aliases = {
        "kylo": "project-kylo",
        "geomapper": "gigatt-geomapper",
        "platform": "gigatt-platform",
        "cog": "cog-allocation",
        "brain": "obsidian-brain",
    }
    if product_id in aliases:
        return product(aliases[product_id])

    # Direct under products/ or root
    for candidate in (products_root() / product_id, root / product_id):
        if _is_dir(candidate):
            return candidate.resolve()
    raise FileNotFoundError(f"Product not found: {product_id}")


@lru_cache(maxsize=1)
def ai_lab_root() -> Path:
    env = os.environ.get("AI_LAB_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if _is_dir(p):
            return p
    return product("ai-lab")


@lru_cache(maxsize=1)
def governance_root() -> Path | None:
    env = os.environ.get("AI_LAB_GOVERNANCE_ROOT", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if _is_dir(p):
            return p
    try:
        return product("ai-lab-governance")
    except FileNotFoundError:
        return None


@lru_cache(maxsize=1)
def vault_root() -> Path:
    for key in ("OPERATOR_BRAIN_VAULT_ROOT", "BRAIN_VAULT_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            p = Path(raw).expanduser().resolve()
            if _is_dir(p):
                return p

    root = repos_root()
    vault = load_layout().get("vault") or {}
    for rel in (vault.get("new_rel"), vault.get("legacy_rel"), "internal/obsidian-brain/Obsidian/Brain", "Ai/Obsidian/Brain"):
        if not rel:
            continue
        candidate = (root / rel.replace("/", os.sep)).resolve()
        if _is_dir(candidate):
            return candidate

    raise FileNotFoundError(
        "Brain vault not found. Set OPERATOR_BRAIN_VAULT_ROOT or BRAIN_VAULT_ROOT."
    )


def growflow_root() -> Path:
    return product("growflow")


def project_kylo_root() -> Path:
    # Prefer live junction on power-1 if present
    junction = Path(r"C:\Project-Kylo")
    if _is_dir(junction):
        return junction.resolve()
    return product("project-kylo")


def layout_status() -> str:
    """Return 'migrated' if products/ exists with project-kylo, else 'legacy'."""
    root = repos_root()
    if _is_dir(root / "products" / "project-kylo") or _is_dir(root / "products" / "ai-lab"):
        return "migrated"
    if _is_dir(root / "Project-Kylo") or _is_dir(root / "ai-lab"):
        return "legacy"
    return "unknown"
