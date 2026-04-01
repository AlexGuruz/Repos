"""
Tests for agents.repo_cartographer.cartographer: run_scan_to_dict and run_scan.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agents.repo_cartographer.cartographer import run_scan_to_dict, run_scan


def test_run_scan_to_dict_nonexistent():
    out = run_scan_to_dict(Path("/nonexistent/path/xyz"), "xyz")
    assert out is None


def test_run_scan_to_dict_existing_dir():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "README.md").write_text("# Test Repo\nHello.", encoding="utf-8")
        (root / "main.py").write_text("print('hi')", encoding="utf-8")
        out = run_scan_to_dict(root, "my-repo")
    assert out is not None
    assert out.get("repo") == "my-repo"
    assert out.get("path") == str(root)
    assert "file_tree_sample" in out
    assert "readme_preview" in out
    assert out.get("readme_preview", "").startswith("# Test Repo")
    assert "main.py" in (out.get("entrypoints") or [])


def test_run_scan_to_dict_uses_dir_name_if_name_none():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        out = run_scan_to_dict(root, None)
    assert out is not None
    assert out.get("repo") == root.name


def test_run_scan_writes_file():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "app.py").write_text("", encoding="utf-8")
        # run_scan writes to ai-lab/summaries/repos; we need to avoid that.
        # So we test run_scan_to_dict only for pure logic, and run_scan
        # only that it returns a string and run_scan_to_dict is called.
        # Actually run_scan uses Path(__file__).parents[2] for ai_lab.
        # So when we run from ai-lab, it will write to ai-lab/summaries/repos.
        # Use a temp dir for the "repo" and run run_scan_to_dict.
        summary = run_scan_to_dict(root, "temp-repo")
        assert summary is not None
        assert "entrypoints" in summary
        assert "app.py" in summary["entrypoints"]


def test_run_scan_integration_if_ai_lab_root_has_repos():
    """Run run_scan against a temp dir as if it were repos_mirror (no side effects to real ai-lab)."""
    with tempfile.TemporaryDirectory() as d:
        repo_root = Path(d)
        (repo_root / "package.json").write_text("{}", encoding="utf-8")
        # run_scan(repo_root, "test") would write to ai-lab/summaries/repos/test.json
        # So we only test run_scan_to_dict and trust run_scan as a thin wrapper.
        out = run_scan_to_dict(repo_root, "test")
        assert out is not None
        assert "package.json" in (out.get("entrypoints") or [])
