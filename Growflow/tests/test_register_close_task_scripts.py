from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_register_close_scheduled_task_helpers_are_committed():
    scripts = ROOT / "scripts"

    assert (scripts / "scheduled_task_pythonw.ps1").is_file()
    assert (scripts / "invoke_python_hidden.ps1").is_file()


def test_register_close_watch_runner_uses_committed_hidden_invoker():
    text = (ROOT / "scripts" / "run_register_close_watch_task.ps1").read_text(encoding="utf-8")

    assert "invoke_python_hidden.ps1" in text
    assert "register_close_taxes_sheet.py" in text
