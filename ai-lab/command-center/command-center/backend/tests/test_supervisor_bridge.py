from __future__ import annotations

import pytest

from services.supervisor_bridge import _normalize_worker_post_body


def test_index_repo_maps_repo_id_under_repos_root():
    body = _normalize_worker_post_body("index_repo", {"repo_id": "Project-Kylo"})

    assert body["repo_path"].endswith("/Project-Kylo")


def test_index_repo_rejects_traversing_repo_id():
    with pytest.raises(ValueError, match="single repository name"):
        _normalize_worker_post_body("index_repo", {"repo_id": "../ai-lab"})


def test_index_repo_rejects_repo_path_outside_repos_root():
    with pytest.raises(ValueError, match="repos root"):
        _normalize_worker_post_body("index_repo", {"repo_path": "/etc"})


def test_index_repo_allows_relative_repo_path_under_repos_root():
    body = _normalize_worker_post_body("index_repo", {"repo_path": "ai-lab"})

    assert body["repo_path"].endswith("/ai-lab")
