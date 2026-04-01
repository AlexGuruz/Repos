"""
GPU metrics collector (Guru §25). Uses nvidia-smi; falls back gracefully if unavailable.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from brain.hardware.schemas.hardware_metrics import GPUMetrics, ProcessInfo


def _nvidia_smi_executable() -> str:
    """
    Resolve nvidia-smi path. On Windows the driver often installs it under NVSMI, not on PATH.
    Override with env NVIDIA_SMI_PATH (full path to nvidia-smi.exe).

    Prefer the real driver NVSMI binary over System32 (some systems ship a stub on PATH first).
    """
    explicit = (os.environ.get("NVIDIA_SMI_PATH") or "").strip().strip('"')
    if explicit:
        return explicit
    if os.name == "nt":
        for pf in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ):
            candidate = os.path.join(pf, "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe")
            if os.path.isfile(candidate):
                return candidate
    w = shutil.which("nvidia-smi")
    if w:
        return w
    if os.name == "nt":
        candidate = os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "NVIDIA Corporation",
            "NVSMI",
            "nvidia-smi.exe",
        )
        if os.path.isfile(candidate):
            return candidate
    return "nvidia-smi"


def get_gpu_metrics() -> GPUMetrics | None:
    """Query nvidia-smi for GPU state. Returns None if no NVIDIA GPU or command fails."""
    try:
        smi = _nvidia_smi_executable()
        result = subprocess.run(
            [
                smi,
                "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            return None
        name, mem_used, mem_total, util, temp = parts[:5]
        mem_used_mb = int(mem_used)
        mem_total_mb = int(mem_total)
        mem_free_mb = max(0, mem_total_mb - mem_used_mb)
        util_pct = int(util) if util.isdigit() else 0
        temp_c = int(temp) if temp.isdigit() else None
        used_pct = (mem_used_mb / mem_total_mb * 100) if mem_total_mb else 0
        available_pct = max(0, 100 - used_pct)
        process_top = _gpu_processes()
        return GPUMetrics(
            name=name.strip(),
            temp_c=float(temp_c) if temp_c is not None else None,
            utilization_percent=float(util_pct),
            vram_used_mb=float(mem_used_mb),
            vram_total_mb=float(mem_total_mb),
            vram_free_mb=float(mem_free_mb),
            used_percent=round(used_pct, 1),
            available_percent=round(available_pct, 1),
            process_top=process_top,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def _gpu_processes() -> list[ProcessInfo]:
    """Per-process GPU memory if nvidia-smi supports it."""
    try:
        smi = _nvidia_smi_executable()
        result = subprocess.run(
            [
                smi,
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return []
        out: list[ProcessInfo] = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                try:
                    pid = int(parts[0])
                    used_mb = float(parts[1].replace(" MiB", "").strip())
                    out.append(ProcessInfo(pid=pid, name="", gpu_memory_mb=used_mb))
                except ValueError:
                    continue
        return out[:10]
    except Exception:
        return []
