#!/usr/bin/env python3
"""
Git staleness for configured repos (local, no Google).

  python scripts/personal_ops_repo_pulse.py --config config/personal_ops.example.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def _load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text)
        except ImportError as e:
            raise SystemExit("Install pyyaml to use YAML configs: pip install pyyaml") from e
    else:
        data = json.loads(text)
    return data if isinstance(data, dict) else {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=_root / "config" / "personal_ops.example.yaml")
    args = ap.parse_args()
    cfg = _load_config(args.config)
    repos = cfg.get("repos") or []
    if not isinstance(repos, list):
        repos = []
    from lib.repo_staleness import scan_repos

    pulses = scan_repos(repos)
    warn_days = float(cfg.get("stale_warning_days") or 7)
    rows = []
    for p in pulses:
        row = {
            "label": p.label,
            "path": p.path,
            "last_commit": p.last_commit_iso,
            "days_idle": p.days_idle,
            "error": p.error,
            "stale": (p.days_idle is not None and p.days_idle >= warn_days),
        }
        rows.append(row)
    print(json.dumps({"stale_warning_days": warn_days, "repos": rows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
