"""Fast-path routing for answer intent (planning + lab summary)."""
from brain.orchestrator.routing_policy import match_answer_fast_path


def test_planning_today_skips_web_heuristic():
    fp = match_answer_fast_path("What should I work on today?")
    assert fp is not None
    assert fp.needs_local is True
    assert fp.needs_web is False
    assert any(t.kind == "ops_registry" for t in fp.local_targets)


def test_lab_summary_includes_readme_when_present():
    fp = match_answer_fast_path("Summarize my ai-lab current state")
    assert fp is not None
    assert fp.needs_web is False
    kinds = [t.kind for t in fp.local_targets]
    assert "ops_registry" in kinds


def test_repo_documentation_status_loads_readme():
    fp = match_answer_fast_path("explain repo documentation status")
    assert fp is not None
    assert fp.needs_web is False
    assert any(t.kind == "artifact" for t in fp.local_targets)
