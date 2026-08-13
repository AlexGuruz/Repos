from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_register_close_powershell_helpers_exist_and_are_referenced() -> None:
    scripts = REPO / "scripts"
    installer = (scripts / "install_register_close_scheduled_task.ps1").read_text(encoding="utf-8")
    runner = (scripts / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")
    task_helper = scripts / "scheduled_task_pythonw.ps1"
    hidden_helper = scripts / "invoke_python_hidden.ps1"

    assert task_helper.is_file()
    assert hidden_helper.is_file()
    assert "scheduled_task_pythonw.ps1" in installer
    assert "New-GrowflowPythonwTaskAction" in task_helper.read_text(encoding="utf-8")
    assert "invoke_python_hidden.ps1" in runner
