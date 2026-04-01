"""Unit tests for source router (PDR Phase 2.75)."""
import pytest
from brain.orchestrator.source_router import route_sources
from brain.orchestrator.freshness import detect_freshness
from brain.orchestrator.session_resolution import resolve_session_references


def _route(msg: str, intent: str = "answer", session: dict | None = None):
    session = session or {"active_topic": None, "last_artifacts": [], "last_failure": None}
    freshness = detect_freshness(msg)
    resolved = resolve_session_references(msg, session)
    return route_sources(
        message=msg,
        intent=intent,
        entities=[],
        session=session,
        freshness=freshness,
        resolved=resolved,
    )


def test_route_local_for_scan_reference():
    session = {"last_artifacts": [{"type": "repo_scan", "summary_path": "/x/summary.md"}], "active_topic": None}
    d = _route("what did that scan tell you", intent="answer", session=session)
    assert d.needs_local is True
    assert d.answer_style_hint == "summary_from_artifact"
    assert len(d.local_targets) >= 1


def test_route_weather_uses_open_meteo_not_web():
    d = _route("what is the weather today")
    assert d.needs_web is False
    assert d.needs_local is True
    assert d.needs_time is True
    weather_targets = [t for t in d.local_targets if t.kind == "weather"]
    assert len(weather_targets) == 1


def test_route_time_only_no_web():
    d = _route("what time is it now")
    assert d.needs_web is False


def test_route_internal_repo():
    d = _route("anything look off in my repos", intent="answer")
    assert d.needs_local is True


def test_route_hardware_status():
    """Guru §25: hardware_status intent adds hardware local target."""
    d = _route("what's my hardware doing right now", intent="hardware_status")
    assert d.needs_local is True
    assert d.answer_style_hint == "direct_status"
    targets = [t for t in d.local_targets if t.kind == "hardware"]
    assert len(targets) == 1
