from __future__ import annotations

from brain.orchestrator.main import _build_worker_repo_scan_command, _normalize_repo_scan_name


def test_repo_scan_name_allows_simple_repo_names() -> None:
    assert _normalize_repo_scan_name("ai-lab") == "ai-lab"
    assert _normalize_repo_scan_name("my.repo_2026") == "my.repo_2026"
    assert _normalize_repo_scan_name("") == "repos_root"


def test_repo_scan_name_rejects_shell_and_path_metacharacters() -> None:
    for raw in ("foo;id", "$(whoami)", "../secret", "a/b", ".", "..", "repo name"):
        assert _normalize_repo_scan_name(raw) is None


def test_worker_repo_scan_command_quotes_remote_path() -> None:
    cmd = _build_worker_repo_scan_command("/tmp/ai lab; touch pwned", "ai-lab")

    assert "cd '/tmp/ai lab; touch pwned'" in cmd
    assert "PYTHONPATH='/tmp/ai lab; touch pwned'" in cmd
    assert cmd.endswith(" ai-lab")
