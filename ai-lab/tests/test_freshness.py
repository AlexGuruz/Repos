"""Unit tests for freshness detection (PDR Phase 2.75)."""
import pytest
from brain.orchestrator.freshness import detect_freshness, FreshnessResult


def test_detect_today():
    r = detect_freshness("what is the weather today")
    assert r.freshness_needed is True
    assert r.needs_time is True
    assert "today" in r.triggers


def test_detect_weather():
    r = detect_freshness("weather in chicago")
    assert "weather" in r.triggers
    assert r.freshness_needed is True


def test_internal_repo_no_freshness():
    r = detect_freshness("scan my repos")
    assert r.freshness_needed is False
    assert r.needs_time is False


def test_empty_message():
    r = detect_freshness("")
    assert r.freshness_needed is False
    assert r.needs_time is False
    assert r.triggers == []


def test_greeting_no_spurious_freshness():
    """Casual chat must not trigger web-search path via substring false positives."""
    r = detect_freshness("hello")
    assert r.freshness_needed is False
    assert r.triggers == []


def test_knowledge_does_not_match_token_now():
    """'now' must not match inside 'knowledge' (old substring bug)."""
    r = detect_freshness("expand on that knowledge base")
    assert r.freshness_needed is False


def test_rapid_does_not_match_token_api():
    """'api' must not match inside 'rapid' (old substring bug)."""
    r = detect_freshness("rapid iteration is fine")
    assert r.freshness_needed is False


def test_explicit_now_still_triggers():
    r = detect_freshness("what time is it now")
    assert r.freshness_needed is True
    assert "now" in r.triggers
