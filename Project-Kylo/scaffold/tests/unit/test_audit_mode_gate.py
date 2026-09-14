from __future__ import annotations

from services.audit.tick import is_audit_mode


class _Config:
    def __init__(self, mode: str) -> None:
        self._mode = mode

    def get(self, key: str, default=None):
        if key == "runtime.mode":
            return self._mode
        return default


def test_allow_post_alone_does_not_disable_audit_mode(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_ALLOW_POST", "1")
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert is_audit_mode(_Config("audit")) is True


def test_post_mode_still_requires_allow_post(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_ALLOW_POST", raising=False)
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert is_audit_mode(_Config("post")) is True


def test_post_mode_with_allow_post_exits_audit_mode(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_ALLOW_POST", "1")
    monkeypatch.delenv("KYLO_RUNTIME_MODE", raising=False)

    assert is_audit_mode(_Config("post")) is False
