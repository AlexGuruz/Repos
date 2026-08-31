from __future__ import annotations

from operator_desk.settings import clear_settings_cache, get_settings


def test_settings_loads_defaults():
    clear_settings_cache()
    s = get_settings(force_reload=True)
    assert s.schema_version == "1"
    assert s.bind_policy == "loopback_only"
    assert s.email_digest_cache_ttl_seconds == 60


def test_settings_env_enable(monkeypatch):
    clear_settings_cache()
    monkeypatch.setenv("OPERATOR_DESK_ENABLED", "1")
    s = get_settings(force_reload=True)
    assert s.enabled is True
    monkeypatch.delenv("OPERATOR_DESK_ENABLED", raising=False)
    clear_settings_cache()
