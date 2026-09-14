"""Static checks for Register Close Windows scheduled-task scripts."""
from __future__ import annotations

from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_scheduled_task_action_helper_exists_and_is_used() -> None:
    install_text = (SCRIPTS / "install_register_close_scheduled_task.ps1").read_text(encoding="utf-8")
    helper = SCRIPTS / "scheduled_task_pythonw.ps1"

    assert "scheduled_task_pythonw.ps1" in install_text
    assert helper.is_file()

    helper_text = helper.read_text(encoding="utf-8")
    assert "function New-GrowflowPythonwTaskAction" in helper_text
    assert "New-ScheduledTaskAction" in helper_text
    assert "invoke_python_hidden.ps1" in helper_text


def test_register_close_task_runner_helper_exists_and_runs_hidden_python() -> None:
    runner_text = (SCRIPTS / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")
    helper = SCRIPTS / "invoke_python_hidden.ps1"

    assert "invoke_python_hidden.ps1" in runner_text
    assert helper.is_file()

    helper_text = helper.read_text(encoding="utf-8")
    assert "$env:PYTHONPATH" in helper_text
    assert "Start-Process" in helper_text
    assert "-WindowStyle Hidden" in helper_text
    assert "exit $process.ExitCode" in helper_text
