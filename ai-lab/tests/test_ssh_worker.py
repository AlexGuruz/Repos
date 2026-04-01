"""
Tests for brain.ssh_worker: get_worker_ssh_config and run_ssh_command.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

from brain.ssh_worker import get_worker_ssh_config, run_ssh_command, SSHResult


def test_get_worker_ssh_config_unset():
    with patch.dict(os.environ, {}, clear=False):
        for key in ("WORKER_SSH_HOST", "WORKER_SSH_USER", "WORKER_AI_LAB_PATH"):
            os.environ.pop(key, None)
        cfg = get_worker_ssh_config()
    assert cfg is None


def test_get_worker_ssh_config_host_only():
    with patch.dict(os.environ, {"WORKER_SSH_HOST": "worker.example.com"}, clear=False):
        os.environ.pop("WORKER_SSH_USER", None)
        os.environ.pop("WORKER_AI_LAB_PATH", None)
        cfg = get_worker_ssh_config()
    assert cfg is not None
    assert cfg["host"] == "worker.example.com"
    assert cfg["user"] is None
    assert cfg["ai_lab_path"] == "."


def test_get_worker_ssh_config_full():
    with patch.dict(
        os.environ,
        {
            "WORKER_SSH_HOST": "worker.local",
            "WORKER_SSH_USER": "deploy",
            "WORKER_AI_LAB_PATH": "/home/deploy/ai-lab",
        },
        clear=False,
    ):
        cfg = get_worker_ssh_config()
    assert cfg["host"] == "worker.local"
    assert cfg["user"] == "deploy"
    assert cfg["ai_lab_path"] == "/home/deploy/ai-lab"


def test_run_ssh_command_returns_ssh_result():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(stdout="ok", stderr="", returncode=0)
        res = run_ssh_command("host", "echo ok")
    assert isinstance(res, SSHResult)
    assert res.stdout == "ok"
    assert res.stderr == ""
    assert res.returncode == 0


def test_run_ssh_command_with_user():
    with patch("subprocess.run") as run:
        run.return_value = MagicMock(stdout="", stderr="", returncode=0)
        run_ssh_command("host", "true", user="alice")
    call_args = run.call_args[0][0]
    assert "alice@host" in call_args
