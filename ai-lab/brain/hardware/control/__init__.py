"""
Approval-gated resource control (Guru §25 Phase 25C). Stubs for priority/affinity/scheduling.
"""
from brain.hardware.control.cpu_affinity import set_cpu_affinity
from brain.hardware.control.process_priority import set_process_priority

__all__ = ["set_cpu_affinity", "set_process_priority"]
