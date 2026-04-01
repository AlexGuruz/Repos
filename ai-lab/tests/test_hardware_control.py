"""
Tests for brain.hardware.control (Guru §25). Process priority and CPU affinity.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from brain.hardware.control import process_priority as pp_mod
from brain.hardware.control import cpu_affinity as ca_mod


def test_set_process_priority_invalid_pid():
    """Invalid pid returns error even when psutil is present."""
    with patch.object(pp_mod, "psutil", MagicMock()):
        from brain.hardware.control.process_priority import set_process_priority
        r = set_process_priority(0, 10)
    assert r["ok"] is False
    assert "Invalid" in r.get("error", "")

    with patch.object(pp_mod, "psutil", MagicMock()):
        from brain.hardware.control.process_priority import set_process_priority
        r = set_process_priority(-1, 10)
    assert r["ok"] is False


def test_set_cpu_affinity_invalid_pid():
    with patch.object(ca_mod, "psutil", MagicMock()):
        from brain.hardware.control.cpu_affinity import set_cpu_affinity
        r = set_cpu_affinity(0, [1, 2])
    assert r["ok"] is False
    assert "Invalid" in r.get("error", "")


def test_set_cpu_affinity_empty_cores():
    with patch.object(ca_mod, "psutil", MagicMock()):
        from brain.hardware.control.cpu_affinity import set_cpu_affinity
        r = set_cpu_affinity(1, [])
    assert r["ok"] is False
    assert "core" in r.get("error", "").lower()


def test_set_process_priority_no_such_process():
    """Non-existent pid returns error (no process 2^30)."""
    try:
        import psutil
    except ImportError:
        pytest.skip("psutil required for no_such_process test")
    from brain.hardware.control.process_priority import set_process_priority
    r = set_process_priority(1073741824, 10)
    assert r["ok"] is False
    err = r.get("error", "").lower()
    assert "not found" in err or "access" in err or "denied" in err or "psutil" in err


def test_set_process_priority_success_mocked():
    with patch.object(pp_mod, "psutil") as m:
        proc = MagicMock()
        m.Process.return_value = proc
        from brain.hardware.control.process_priority import set_process_priority
        r = set_process_priority(12345, 10)
    assert r["ok"] is True
    assert r.get("error") == ""


def test_set_cpu_affinity_success_mocked():
    with patch.object(ca_mod, "psutil") as m:
        proc = MagicMock()
        m.Process.return_value = proc
        from brain.hardware.control.cpu_affinity import set_cpu_affinity
        r = set_cpu_affinity(12345, [2, 3])
    assert r["ok"] is True
    proc.cpu_affinity.assert_called_once_with([2, 3])
