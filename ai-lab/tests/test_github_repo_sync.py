from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_sync_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "github_repo_sync.py"
    name = "github_repo_sync_under_test"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parse_branch_status_ahead_behind() -> None:
    m = _load_sync_module()
    has_u, ahead, behind = m._parse_branch_status("## main...origin/main [ahead 2, behind 17]")
    assert has_u is True
    assert ahead == 2
    assert behind == 17


def test_parse_branch_status_clean_tracking() -> None:
    m = _load_sync_module()
    has_u, ahead, behind = m._parse_branch_status("## main...origin/main")
    assert has_u is True
    assert ahead == 0
    assert behind == 0


def test_parse_branch_status_no_upstream() -> None:
    m = _load_sync_module()
    has_u, ahead, behind = m._parse_branch_status("## master")
    assert has_u is False


def test_is_dirty() -> None:
    m = _load_sync_module()
    assert m._is_dirty(" M foo.txt\n") is True
    assert m._is_dirty("") is False
