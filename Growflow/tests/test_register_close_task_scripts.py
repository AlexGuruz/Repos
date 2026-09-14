from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_register_close_scheduled_task_helpers_exist():
    assert (SCRIPTS / "scheduled_task_pythonw.ps1").is_file()
    assert (SCRIPTS / "invoke_python_hidden.ps1").is_file()


def test_register_close_task_scripts_reference_existing_helpers():
    install = (SCRIPTS / "install_register_close_scheduled_task.ps1").read_text(encoding="utf-8")
    runner = (SCRIPTS / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")

    assert "scheduled_task_pythonw.ps1" in install
    assert "New-GrowflowPythonwTaskAction" in install
    assert "invoke_python_hidden.ps1" in runner
    assert "register_close_taxes_sheet.py" in runner
