"""
Hardware metrics schema (Guru §25). Normalized CPU/GPU/process snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float = 0.0
    gpu_memory_mb: float | None = None
    priority: int | None = None
    affinity: list[int] | None = None


@dataclass
class CPUMetrics:
    package_temp_c: float | None = None
    total_usage_percent: float = 0.0
    available_percent: float = 100.0
    used_percent: float = 0.0
    frequency_current_mhz: float | None = None
    frequency_max_mhz: float | None = None
    per_core_usage_percent: list[float] = field(default_factory=list)
    per_core_temp_c: list[float] = field(default_factory=list)
    process_top: list[ProcessInfo] = field(default_factory=list)


@dataclass
class GPUMetrics:
    name: str = ""
    temp_c: float | None = None
    utilization_percent: float = 0.0
    vram_used_mb: float = 0.0
    vram_total_mb: float = 0.0
    vram_free_mb: float = 0.0
    available_percent: float = 100.0
    used_percent: float = 0.0
    power_w: float | None = None
    fan_percent: float | None = None
    process_top: list[ProcessInfo] = field(default_factory=list)


@dataclass
class HardwareSnapshot:
    """Full hardware snapshot for assistant and Compute panel."""
    timestamp: str = ""
    node: str = "local"
    cpu: CPUMetrics = field(default_factory=CPUMetrics)
    gpu: GPUMetrics | None = None
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API and telemetry. Includes legacy keys for existing frontend."""
        d: dict[str, Any] = {
            "timestamp": self.timestamp,
            "node": self.node,
            "cpu": {
                "package_temp_c": self.cpu.package_temp_c,
                "total_usage_percent": self.cpu.total_usage_percent,
                "available_percent": self.cpu.available_percent,
                "used_percent": self.cpu.used_percent,
                "frequency_current_mhz": self.cpu.frequency_current_mhz,
                "frequency_max_mhz": self.cpu.frequency_max_mhz,
                "per_core_usage_percent": self.cpu.per_core_usage_percent,
                "per_core_temp_c": self.cpu.per_core_temp_c,
                "process_top": [
                    {
                        "pid": p.pid,
                        "name": p.name,
                        "cpu_percent": p.cpu_percent,
                        "priority": p.priority,
                        "affinity": p.affinity,
                        "gpu_memory_mb": p.gpu_memory_mb,
                    }
                    for p in self.cpu.process_top
                ],
            },
            "ram_used_gb": self.ram_used_gb,
            "ram_total_gb": self.ram_total_gb,
        }
        if self.gpu:
            d["gpu"] = {
                "name": self.gpu.name,
                "temp_c": self.gpu.temp_c,
                "utilization_percent": self.gpu.utilization_percent,
                "vram_used_mb": self.gpu.vram_used_mb,
                "vram_total_mb": self.gpu.vram_total_mb,
                "vram_free_mb": self.gpu.vram_free_mb,
                "available_percent": self.gpu.available_percent,
                "used_percent": self.gpu.used_percent,
                "power_w": self.gpu.power_w,
                "fan_percent": self.gpu.fan_percent,
                "process_top": [
                    {"pid": p.pid, "name": p.name, "gpu_memory_mb": p.gpu_memory_mb}
                    for p in self.gpu.process_top
                ],
            }
            # Legacy shape for existing frontend
            d["gpu_legacy"] = {
                "name": self.gpu.name,
                "vram_used_gb": round(self.gpu.vram_used_mb / 1024, 1),
                "vram_total_gb": round(self.gpu.vram_total_mb / 1024, 1),
                "utilization_pct": int(self.gpu.utilization_percent),
                "temp_c": int(self.gpu.temp_c) if self.gpu.temp_c is not None else None,
            }
        else:
            d["gpu"] = None
            d["gpu_legacy"] = None
        d["cpu_percent"] = self.cpu.total_usage_percent
        return d

    def to_assistant_text(self) -> str:
        """Human-readable summary for LLM evidence."""
        lines = [
            f"Hardware snapshot at {self.timestamp} (node: {self.node})",
            "",
            "CPU:",
            f"  Total usage: {self.cpu.total_usage_percent:.1f}%",
            f"  Available: {self.cpu.available_percent:.1f}%",
        ]
        if self.cpu.package_temp_c is not None:
            lines.append(f"  Package temp: {self.cpu.package_temp_c:.0f}°C")
        if self.cpu.per_core_usage_percent:
            lines.append(f"  Per-core usage: {', '.join(f'{u:.0f}%' for u in self.cpu.per_core_usage_percent[:8])}")
        if self.cpu.process_top:
            lines.append("  Top processes:")
            for p in self.cpu.process_top[:8]:
                lines.append(f"    - {p.name} (pid {p.pid}): {p.cpu_percent:.1f}% CPU")
        lines.append("")
        lines.append(f"RAM: {self.ram_used_gb:.1f} GB / {self.ram_total_gb:.1f} GB used")
        lines.append("")
        if self.gpu:
            lines.append("GPU:")
            lines.append(f"  Name: {self.gpu.name}")
            lines.append(f"  Utilization: {self.gpu.utilization_percent:.1f}%")
            lines.append(f"  VRAM: {self.gpu.vram_used_mb:.0f} / {self.gpu.vram_total_mb:.0f} MB ({self.gpu.used_percent:.1f}% used)")
            if self.gpu.temp_c is not None:
                lines.append(f"  Temp: {self.gpu.temp_c:.0f}°C")
            if self.gpu.process_top:
                lines.append("  Top GPU processes:")
                for p in self.gpu.process_top[:5]:
                    mem = f" {p.gpu_memory_mb:.0f} MB" if p.gpu_memory_mb else ""
                    lines.append(f"    - {p.name} (pid {p.pid}){mem}")
        else:
            lines.append("GPU: not available")
        return "\n".join(lines)
