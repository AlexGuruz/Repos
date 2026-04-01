"""
Hardware observability (Guru §25). CPU/GPU monitoring, process attribution, telemetry.
"""
from brain.hardware.collectors import get_snapshot

__all__ = ["get_snapshot"]
