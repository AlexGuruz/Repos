"""Tests for repos_paths dual-read helpers."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import repos_paths as rp  # noqa: E402


def setup_function(_):
    rp.clear_caches()


def test_layout_loads():
    layout = rp.load_layout()
    assert "moves" in layout
    assert any(m["id"] == "project-kylo" for m in layout["moves"])


def test_repos_root_exists():
    root = rp.repos_root()
    assert root.is_dir()
    assert (root / "tools" / "migration" / "layout.json").is_file() or (
        root / "tools" / "migration"
    ).is_dir()


def test_layout_status_legacy_or_migrated():
    status = rp.layout_status()
    assert status in ("legacy", "migrated", "unknown")


def test_product_ai_lab():
    p = rp.product("ai-lab")
    assert p.is_dir()
    assert p.name in ("ai-lab",)


def test_product_growflow():
    p = rp.product("growflow")
    assert p.is_dir()


def test_product_gigatt_platform():
    p = rp.product("gigatt-platform")
    assert p.is_dir()
    assert p.name == "gigatt-platform"


def test_ai_lab_root_matches_product():
    assert rp.ai_lab_root() == rp.product("ai-lab")
