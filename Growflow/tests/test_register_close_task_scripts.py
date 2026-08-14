from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_register_close_scheduled_task_helpers_are_committed():
    install = SCRIPTS / "install_register_close_scheduled_task.ps1"
    runner = SCRIPTS / "run_register_close_watch_task.ps1"
    scheduled_helper = SCRIPTS / "scheduled_task_pythonw.ps1"
    invoke_helper = SCRIPTS / "invoke_python_hidden.ps1"

    assert scheduled_helper.is_file()
    assert invoke_helper.is_file()
    assert "scheduled_task_pythonw.ps1" in install.read_text(encoding="utf-8")
    assert "invoke_python_hidden.ps1" in runner.read_text(encoding="utf-8")

    scheduled_text = scheduled_helper.read_text(encoding="utf-8")
    invoke_text = invoke_helper.read_text(encoding="utf-8")
    assert "function Resolve-GrowflowPythonw" in scheduled_text
    assert "function New-GrowflowPythonwTaskAction" in scheduled_text
    assert "Resolve-GrowflowPythonw" in invoke_text
    assert "Start-Process" in invoke_text
