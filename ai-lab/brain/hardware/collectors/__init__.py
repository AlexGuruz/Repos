"""
Hardware collectors (Guru §25). CPU, GPU, process metrics.
"""
from brain.hardware.collectors.snapshot import get_snapshot

__all__ = ["get_snapshot"]
