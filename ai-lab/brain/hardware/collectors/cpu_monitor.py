"""
CPU metrics collector (Guru §25). Package/core temps, usage, frequency, top processes.
"""
from __future__ import annotations

import os
from brain.hardware.schemas.hardware_metrics import CPUMetrics, ProcessInfo

try:
    import psutil
except ImportError:
    psutil = None


def get_cpu_metrics() -> CPUMetrics:
    """Collect CPU metrics. Returns zeroed struct if psutil unavailable."""
    if not psutil:
        return CPUMetrics()

    # interval=None first call is always 0.0 (psutil docs). Use a short blocking sample.
    try:
        total = float(psutil.cpu_percent(interval=0.08))
    except Exception:
        total = 0.0
    used = total
    available = max(0.0, 100.0 - total)

    # CPU temperature:
    # - psutil.sensors_temperatures() is platform-dependent; may return empty dict.
    # - We pick the max "current" temperature as a reasonable "package" proxy.
    package_temp_c: float | None = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            candidates: list[float] = []
            for _chip, entries in temps.items():
                for t in entries:
                    cur = getattr(t, "current", None)
                    if cur is None:
                        continue
                    # Filter out obviously bogus readings
                    if isinstance(cur, (int, float)) and cur > -40 and cur < 200:
                        candidates.append(float(cur))
            if candidates:
                package_temp_c = max(candidates)
    except Exception:
        package_temp_c = None

    per_core: list[float] = []
    try:
        # After one interval-based sample above, per-CPU None reads are meaningful (no second delay).
        per_core = [float(x) for x in (psutil.cpu_percent(interval=None, percpu=True) or [])]
    except Exception:
        pass

    freq_current: float | None = None
    freq_max: float | None = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            freq_current = freq.current
            freq_max = freq.max or freq.current
    except Exception:
        pass

    process_top = _top_cpu_processes(limit=10)
    return CPUMetrics(
        package_temp_c=package_temp_c,
        total_usage_percent=round(total, 1),
        available_percent=round(available, 1),
        used_percent=round(used, 1),
        frequency_current_mhz=freq_current,
        frequency_max_mhz=freq_max,
        per_core_usage_percent=[round(x, 1) for x in per_core],
        process_top=process_top,
    )


def _top_cpu_processes(limit: int = 10) -> list[ProcessInfo]:
    if not psutil:
        return []
    procs: list[tuple[float, ProcessInfo]] = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "nice"]):
        try:
            info = p.info
            cpu = (info.get("cpu_percent") or 0) or 0.0
            if cpu <= 0:
                continue
            name = (info.get("name") or "").strip() or f"pid_{info.get('pid', 0)}"
            if len(name) > 50:
                name = name[:47] + "..."
            nice = info.get("nice")
            priority = int(nice) if nice is not None else None
            procs.append((cpu, ProcessInfo(pid=info.get("pid", 0), name=name, cpu_percent=cpu, priority=priority)))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x[0], reverse=True)
    return [p[1] for p in procs[:limit]]
