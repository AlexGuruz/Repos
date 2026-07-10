#!/usr/bin/env python3
"""
POST each discover_*.graphql under scripts/growflow_discovery_queries/ to GrowFlow GraphQL.

Use for quick validation when SDL or an introspection-enabled URL is available.
Does not change planner logic. See scripts/growflow_discovery_queries/README.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Repo root on sys.path for `lib`
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib.growflow_graphql import graphql_request, resolve_graphql_url  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Run GrowFlow discovery GraphQL files.")
    p.add_argument(
        "--credentials",
        default=None,
        help="Path to GrowFlow credentials file (else env / default discovery).",
    )
    p.add_argument(
        "--graphql-url",
        default=None,
        help="Override GraphQL POST URL (else GROWFLOW_GRAPHQL_URL / org env).",
    )
    p.add_argument(
        "--dir",
        type=Path,
        default=_ROOT / "scripts" / "growflow_discovery_queries",
        help="Directory containing discover_*.graphql",
    )
    p.add_argument(
        "--only",
        default=None,
        help="Substring of filename to run (e.g. findProducts).",
    )
    p.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Exit non-zero on first HTTP failure or GraphQL errors.",
    )
    args = p.parse_args()
    d: Path = args.dir
    if not d.is_dir():
        print(f"Not a directory: {d}", file=sys.stderr)
        return 2

    files = sorted(d.glob("discover_*.graphql"))
    if args.only:
        files = [f for f in files if args.only in f.name]
    if not files:
        print(f"No discover_*.graphql in {d}", file=sys.stderr)
        return 2

    url = resolve_graphql_url(args.graphql_url)
    print(f"POST {url}", flush=True)

    any_fail = False
    for path in files:
        query = path.read_text(encoding="utf-8")
        print(f"\n=== {path.name} ===", flush=True)
        try:
            body = graphql_request(
                query,
                variables=None,
                credentials_path=args.credentials,
                graphql_url=args.graphql_url,
            )
        except ValueError as e:
            print(f"Credentials: {e}", flush=True)
            return 2
        except RuntimeError as e:
            print(f"HTTP / network: {e}", flush=True)
            any_fail = True
            if args.stop_on_error:
                return 1
            continue

        errs = body.get("errors")
        if errs:
            print("GraphQL errors:", flush=True)
            print(json.dumps(errs, indent=2)[:4000], flush=True)
            any_fail = True
            if args.stop_on_error:
                return 1
        else:
            # Short success line (avoid dumping huge payloads)
            data = body.get("data")
            keys = list(data.keys()) if isinstance(data, dict) else []
            print(f"OK data keys: {keys}", flush=True)

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
