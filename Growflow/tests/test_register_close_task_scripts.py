from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RegisterCloseTaskScriptTests(unittest.TestCase):
    def test_scheduled_task_scripts_do_not_reference_missing_helpers(self) -> None:
        install_script = (ROOT / "scripts" / "install_register_close_scheduled_task.ps1").read_text(
            encoding="utf-8"
        )
        task_script = (ROOT / "scripts" / "run_register_close_watch_task.ps1").read_text(
            encoding="utf-8"
        )

        combined = install_script + "\n" + task_script
        self.assertNotIn("scheduled_task_pythonw.ps1", combined)
        self.assertNotIn("invoke_python_hidden.ps1", combined)

    def test_scheduled_task_uses_checked_in_runner(self) -> None:
        install_script = (ROOT / "scripts" / "install_register_close_scheduled_task.ps1").read_text(
            encoding="utf-8"
        )

        self.assertTrue((ROOT / "scripts" / "run_register_close_watch_task.ps1").is_file())
        self.assertIn("New-ScheduledTaskAction", install_script)
        self.assertIn("run_register_close_watch_task.ps1", install_script)


if __name__ == "__main__":
    unittest.main()
