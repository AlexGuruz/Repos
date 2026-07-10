"""
Ops registry reader (Guru §23 Phase 4). Load systems, workers, automations for assistant evidence.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

_OPS_SUMMARY_CACHE: tuple[float, str] | None = None
_OPS_SUMMARY_TTL_SEC = 300.0


def get_ops_root() -> Path:
    """Return ops directory root. Default: ai-lab/ops; override with OPS_ROOT."""
    env = os.environ.get("OPS_ROOT", "").strip()
    if env:
        return Path(env)
    root = Path(__file__).resolve().parents[1]
    return root / "ops"


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8")
        try:
            import yaml
            return yaml.safe_load(text) or {}
        except ImportError:
            # Minimal YAML parse for "key:\n  k2: v" style
            out: dict[str, Any] = {}
            key = None
            for line in text.splitlines():
                if ":" in line and not line.strip().startswith("#"):
                    k, _, v = line.partition(":")
                    k = k.strip()
                    v = v.strip()
                    if not k:
                        continue
                    if line[0] not in " \t" and key is None:
                        out[k] = v if v else {}
                        key = k
                    elif line[0] not in " \t":
                        key = k
                        out[k] = v if v else {}
            return out
    except Exception:
        return {}


def load_systems(ops_root: Path | None = None) -> dict[str, Any]:
    """Load systems registry. Returns { systems: { name: {...} } }."""
    root = ops_root or get_ops_root()
    data = _load_yaml(root / "registry" / "systems.yaml")
    return data if isinstance(data, dict) else {}


def load_workers(ops_root: Path | None = None) -> dict[str, Any]:
    """Load workers registry."""
    root = ops_root or get_ops_root()
    data = _load_yaml(root / "registry" / "workers.yaml")
    return data if isinstance(data, dict) else {}


def load_automations(ops_root: Path | None = None) -> dict[str, Any]:
    """Load automations registry."""
    root = ops_root or get_ops_root()
    data = _load_yaml(root / "registry" / "automations.yaml")
    return data if isinstance(data, dict) else {}


def get_ops_summary_text(ops_root: Path | None = None) -> str:
    """Single text summary of ops registries for LLM evidence."""
    root = ops_root or get_ops_root()
    lines = ["# Operations registry summary", ""]

    systems = load_systems(root)
    sys_list = systems.get("systems") if isinstance(systems.get("systems"), dict) else {}
    if sys_list:
        lines.append("## Systems")
        for name, info in sys_list.items():
            if isinstance(info, dict):
                purpose = info.get("purpose") or info.get("type") or ""
                repo = info.get("repo") or ""
                workers = info.get("workers") or []
                lines.append(f"- **{name}**: {purpose}; repo={repo}; workers={workers}")
        lines.append("")

    workers = load_workers(root)
    wrk_list = workers.get("workers") if isinstance(workers.get("workers"), dict) else {}
    if wrk_list:
        lines.append("## Workers")
        for name, info in wrk_list.items():
            if isinstance(info, dict):
                purpose = info.get("purpose") or ""
                caps = info.get("capabilities") or []
                lines.append(f"- **{name}**: {purpose}; capabilities={caps}")
        lines.append("")

    autos = load_automations(root)
    auto_list = autos.get("automations") if isinstance(autos.get("automations"), dict) else {}
    if auto_list:
        lines.append("## Automations")
        for name, info in auto_list.items():
            if isinstance(info, dict):
                desc = info.get("description") or ""
                status = info.get("status") or "unknown"
                lines.append(f"- **{name}**: {desc}; status={status}")
        lines.append("")

    if not (sys_list or wrk_list or auto_list):
        lines.append("(No registry data found. Add ops/registry/systems.yaml, workers.yaml, automations.yaml.)")

    return "\n".join(lines)


def get_ops_summary_text_cached(ops_root: Path | None = None, *, ttl_sec: float = _OPS_SUMMARY_TTL_SEC) -> str:
    """Cached variant for hot chat paths (ops_overview / planning fast-path)."""
    global _OPS_SUMMARY_CACHE
    now = time.monotonic()
    if _OPS_SUMMARY_CACHE and (now - _OPS_SUMMARY_CACHE[0]) < ttl_sec:
        return _OPS_SUMMARY_CACHE[1]
    text = get_ops_summary_text(ops_root)
    _OPS_SUMMARY_CACHE = (now, text)
    return text
