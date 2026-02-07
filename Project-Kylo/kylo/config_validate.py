"""
Validate `config/kylo.config.yaml` against the Pydantic schema.

Usage:
    python bin/validate_config.py [--path PATH]
"""

import argparse
import json
import sys
from pathlib import Path

from services.common.config_loader import load_config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate kylo.config.yaml")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Optional path to config file (defaults to config/kylo.config.yaml or KYLO_CONFIG_PATH)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the normalized configuration as JSON",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        cfg = load_config(path=str(args.path) if args.path else None)
    except Exception as exc:  # pragma: no cover - surfaced as a CLI failure
        print(f"[error] Invalid configuration: {exc}", file=sys.stderr)
        return 1

    data = cfg.model.model_dump(mode="json")
    companies = len(data.get("sheets", {}).get("companies", []) or [])

    print("[ok] kylo.config.yaml validated successfully")
    print(f"Version: {data.get('version', 'n/a')} | Companies configured: {companies}")
    if args.pretty:
        print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


