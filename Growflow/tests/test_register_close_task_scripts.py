from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def test_register_close_task_scripts_do_not_reference_missing_helpers():
    scripts = [
        REPO / "scripts" / "run_register_close_watch_task.ps1",
        REPO / "scripts" / "install_register_close_scheduled_task.ps1",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scripts)

    assert "invoke_python_hidden.ps1" not in combined
    assert "scheduled_task_pythonw.ps1" not in combined
    assert "run_register_close_watch_task.ps1" in combined
    assert "register_close_taxes_sheet.py" in combined
