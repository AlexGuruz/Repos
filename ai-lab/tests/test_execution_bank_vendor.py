from __future__ import annotations

from brain.execution import _cli_args_from_dict, run_bank_vendor_cleaner


def test_cli_args_dry_run_flag() -> None:
    argv = _cli_args_from_dict({"dry_run": True, "spreadsheet_id": "abc"})
    assert "--dry-run" in argv
    assert "--spreadsheet-id" in argv
    assert "abc" in argv


def test_run_bank_vendor_cleaner_dry_run_blocked_without_google(monkeypatch) -> None:
    """Dry-run still needs Sheets read; expect failure before write if auth/sheet missing."""
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.delenv("GOOGLE_CREDENTIALS_FILE", raising=False)
    result = run_bank_vendor_cleaner({"dry_run": True})
    assert not result.success
