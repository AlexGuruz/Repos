"""Unit tests for approval gate (PDR Phase 2.75)."""
import pytest
from brain.orchestrator.approval_gate import requires_approval, AUTO_ALLOWED, APPROVAL_REQUIRED


def test_read_only_allowed():
    assert requires_approval("repo_search") is False
    assert requires_approval("scan") is False
    assert requires_approval("web_search") is False


def test_write_requires_approval():
    assert requires_approval("patch_registry") is True
    assert requires_approval("edit") is True
    assert requires_approval("commit") is True


def test_tool_param():
    assert requires_approval("run", tool="repo_search") is False
    assert requires_approval("run", tool="patch_registry") is True


def test_hardware_control_requires_approval():
    """Guru §25: process priority and CPU affinity are approval-gated."""
    assert requires_approval("set_process_priority") is True
    assert requires_approval("set_cpu_affinity") is True
    assert requires_approval("process_priority") is True
    assert requires_approval("cpu_affinity") is True
