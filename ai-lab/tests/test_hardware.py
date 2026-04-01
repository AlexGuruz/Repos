"""
Tests for brain.hardware (Guru §25). Snapshot, schema, alerts.
"""
from __future__ import annotations

import pytest

from brain.hardware.schemas.hardware_metrics import (
    HardwareSnapshot,
    CPUMetrics,
    GPUMetrics,
    ProcessInfo,
)
from brain.hardware.collectors.snapshot import get_snapshot
from brain.hardware.telemetry.alerts import check_thresholds


def test_snapshot_returns_structured_data():
    """get_snapshot() returns HardwareSnapshot with cpu and optional gpu."""
    s = get_snapshot()
    assert isinstance(s, HardwareSnapshot)
    assert s.timestamp
    assert isinstance(s.cpu, CPUMetrics)
    assert 0 <= s.cpu.total_usage_percent <= 100
    assert s.ram_total_gb >= 0


def test_snapshot_to_dict_has_legacy_keys():
    """to_dict() includes legacy gpu/cpu_percent for existing frontend."""
    s = get_snapshot()
    d = s.to_dict()
    assert "cpu_percent" in d
    assert "ram_used_gb" in d
    assert "ram_total_gb" in d
    assert "timestamp" in d
    assert "gpu" in d or "gpu_legacy" in d


def test_snapshot_to_assistant_text():
    """to_assistant_text() returns non-empty string for LLM evidence."""
    s = get_snapshot()
    text = s.to_assistant_text()
    assert "CPU" in text
    assert "RAM" in text
    assert len(text) > 100


def test_check_thresholds_no_alert_on_low_usage():
    """check_thresholds returns empty list when usage is normal."""
    s = HardwareSnapshot(
        timestamp="",
        node="local",
        cpu=CPUMetrics(total_usage_percent=50.0),
        gpu=GPUMetrics(used_percent=50.0, temp_c=60.0),
        ram_used_gb=8,
        ram_total_gb=16,
    )
    alerts = check_thresholds(s)
    assert isinstance(alerts, list)
    assert len(alerts) == 0


def test_check_thresholds_alert_on_high_cpu():
    """check_thresholds flags very high CPU."""
    s = HardwareSnapshot(
        timestamp="",
        node="local",
        cpu=CPUMetrics(total_usage_percent=96.0),
        gpu=None,
        ram_used_gb=8,
        ram_total_gb=16,
    )
    alerts = check_thresholds(s)
    assert any("CPU" in a for a in alerts)


def test_check_thresholds_alert_on_high_gpu_temp():
    """check_thresholds flags high GPU temp."""
    s = HardwareSnapshot(
        timestamp="",
        node="local",
        cpu=CPUMetrics(total_usage_percent=20.0),
        gpu=GPUMetrics(temp_c=88.0, used_percent=50.0),
        ram_used_gb=8,
        ram_total_gb=16,
    )
    alerts = check_thresholds(s)
    assert any("temperature" in a.lower() or "temp" in a.lower() for a in alerts)
