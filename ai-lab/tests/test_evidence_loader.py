"""Unit tests for evidence loader (PDR Phase 2.75)."""
import pytest
import tempfile
from pathlib import Path
from brain.orchestrator.evidence_loader import load_evidence
from brain.schemas.routing import RoutingDecision, LocalTarget


def test_load_artifact(tmp_path):
    md = tmp_path / "summary.md"
    md.write_text("# Scan\nTop finding: missing README.")
    decision = RoutingDecision(
        intent="answer",
        needs_local=True,
        local_targets=[LocalTarget(kind="artifact", path=str(md), priority=1)],
    )
    # session_id used for session state; use a unique one to avoid cross-test state
    out = load_evidence(decision, "test_load_artifact")
    assert len(out.local_evidence) == 1
    assert out.local_evidence[0].source_type == "markdown_summary"
    assert "missing README" in (out.local_evidence[0].content or "")


def test_load_config(tmp_path):
    cfg = tmp_path / "scripts.json"
    cfg.write_text('{"scripts": []}')
    decision = RoutingDecision(
        intent="answer",
        needs_local=True,
        local_targets=[LocalTarget(kind="config", path=str(cfg), priority=1)],
    )
    out = load_evidence(decision, "test_load_config")
    assert len(out.local_evidence) == 1
    assert out.local_evidence[0].source_type == "config"
    assert "scripts" in (out.local_evidence[0].content or "")


def test_load_missing_path():
    decision = RoutingDecision(
        intent="answer",
        needs_local=True,
        local_targets=[LocalTarget(kind="artifact", path="/nonexistent/path.md", priority=1)],
    )
    out = load_evidence(decision, "test_missing")
    assert len(out.local_evidence) == 0
    assert len(out.notes) >= 1


def test_load_hardware():
    """Guru §25: hardware target loads snapshot and adds hardware_snapshot evidence."""
    decision = RoutingDecision(
        intent="hardware_status",
        needs_local=True,
        local_targets=[LocalTarget(kind="hardware", reason="User asked about hardware.")],
    )
    out = load_evidence(decision, "test_load_hardware")
    assert len(out.local_evidence) >= 1
    hw = next((e for e in out.local_evidence if e.source_type == "hardware_snapshot"), None)
    assert hw is not None
    assert "CPU" in (hw.content or "")
    assert "RAM" in (hw.content or "")
