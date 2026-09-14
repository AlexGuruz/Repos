from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"


def test_register_close_task_helpers_exist_and_are_referenced() -> None:
    scheduled_helper = SCRIPTS / "scheduled_task_pythonw.ps1"
    hidden_helper = SCRIPTS / "invoke_python_hidden.ps1"
    install_script = SCRIPTS / "install_register_close_scheduled_task.ps1"
    run_task_script = SCRIPTS / "run_register_close_watch_task.ps1"

    assert scheduled_helper.is_file()
    assert hidden_helper.is_file()
    assert "scheduled_task_pythonw.ps1" in install_script.read_text(encoding="utf-8")
    assert "invoke_python_hidden.ps1" in run_task_script.read_text(encoding="utf-8")
    assert "Resolve-GrowflowPythonw" in scheduled_helper.read_text(encoding="utf-8")
    assert "New-GrowflowPythonwTaskAction" in scheduled_helper.read_text(encoding="utf-8")
