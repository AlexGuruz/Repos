from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_register_close_scheduled_task_helpers_exist() -> None:
    installer = (SCRIPTS / "install_register_close_scheduled_task.ps1").read_text(encoding="utf-8")
    action_helper = SCRIPTS / "scheduled_task_pythonw.ps1"
    invoke_helper = SCRIPTS / "invoke_python_hidden.ps1"

    assert action_helper.is_file()
    assert invoke_helper.is_file()
    assert "scheduled_task_pythonw.ps1" in installer
    assert "New-GrowflowPythonwTaskAction" in action_helper.read_text(encoding="utf-8")
    assert "register_close_taxes_sheet.py" in (SCRIPTS / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")
