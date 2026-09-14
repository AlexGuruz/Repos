from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_register_close_installer_uses_committed_runner():
    text = (ROOT / "scripts" / "install_register_close_scheduled_task.ps1").read_text(encoding="utf-8")

    assert "run_register_close_watch_task.ps1" in text
    assert "scheduled_task_pythonw.ps1" not in text


def test_register_close_watch_runner_is_self_contained():
    text = (ROOT / "scripts" / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")

    assert "register_close_taxes_sheet.py" in text
    assert "$env:PYTHONPATH" in text
    assert "invoke_python_hidden.ps1" not in text
