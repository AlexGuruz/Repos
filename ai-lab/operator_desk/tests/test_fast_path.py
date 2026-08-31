from __future__ import annotations

from operator_desk.fast_path import try_fast_reply
from operator_desk.settings import clear_settings_cache


def test_fast_path_disabled_by_default(monkeypatch):
    clear_settings_cache()
    monkeypatch.delenv("OPERATOR_DESK_ENABLED", raising=False)
    assert try_fast_reply("Where are we on Growflow today?") is None


def test_fast_path_growflow(monkeypatch, tmp_snapshot):
    clear_settings_cache()
    monkeypatch.setenv("OPERATOR_DESK_ENABLED", "1")
    monkeypatch.setenv("OPERATOR_JOBS_DIR", str(__file__).replace("test_fast_path.py", "fixtures/jobs"))
    from operator_desk.job_primer import clear_manifest_cache

    clear_manifest_cache()
    clear_settings_cache()
    out = try_fast_reply("Where are we on Growflow today?")
    assert out is not None
    assert "Test snapshot" in out["reply"]
    clear_settings_cache()
    monkeypatch.delenv("OPERATOR_DESK_ENABLED", raising=False)
