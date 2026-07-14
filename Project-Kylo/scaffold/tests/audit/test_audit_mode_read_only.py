from __future__ import annotations

from services.audit.tick import _sheets_writes_blocked


class _Cfg:
    def __init__(self, mode: str) -> None:
        self.mode = mode

    def get(self, dotted: str, default=None):
        if dotted == "runtime.mode":
            return self.mode
        return default


def test_audit_mode_blocks_sheet_highlights_and_notes(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_ALLOW_POST", raising=False)
    monkeypatch.delenv("KYLO_READ_ONLY", raising=False)
    monkeypatch.delenv("KYLO_SHEETS_DRY_RUN", raising=False)
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert _sheets_writes_blocked(_Cfg("audit")) is True


def test_post_mode_allows_sheet_writes_when_not_read_only(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_ALLOW_POST", raising=False)
    monkeypatch.delenv("KYLO_READ_ONLY", raising=False)
    monkeypatch.delenv("KYLO_SHEETS_DRY_RUN", raising=False)
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert _sheets_writes_blocked(_Cfg("post")) is False


def test_read_only_env_still_blocks_post_mode(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_ALLOW_POST", raising=False)
    monkeypatch.setenv("KYLO_READ_ONLY", "1")
    monkeypatch.delenv("KYLO_SHEETS_DRY_RUN", raising=False)
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert _sheets_writes_blocked(_Cfg("post")) is True
