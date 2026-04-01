#!/usr/bin/env python3
"""
Read tool/repo/agent registry. Used by supervisor and wrappers to enforce
'reuse first' — check registry before creating or running scripts.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _governance_root() -> Path:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if root:
        return Path(root)
    return Path(__file__).resolve().parent.parent


def load_tool_registry(root: Path) -> dict:
    p = root / "registry" / "tool_registry.json"
    if not p.exists():
        return {"version": "1.0", "tools": {}}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read governance registry")
    ap.add_argument("registry", choices=["tool", "repo", "agent"], help="Which registry")
    ap.add_argument("--query", default="", help="Optional: key or pattern to look up")
    ap.add_argument("--json", action="store_true", help="Output full JSON")
    args = ap.parse_args()

    root = _governance_root()
    if args.registry == "tool":
        data = load_tool_registry(root)
        if args.query:
            tools = data.get("tools", {})
            if args.query in tools:
                out = tools[args.query] if not args.json else {args.query: tools[args.query]}
            else:
                out = {k: v for k, v in tools.items() if args.query.lower() in k.lower() or args.query in str(v).lower()}
            print(json.dumps(out, indent=2))
        else:
            print(json.dumps(data, indent=2) if args.json else "\n".join(data.get("tools", {}).keys()))
    elif args.registry == "repo":
        p = root / "registry" / "repo_registry.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"repos": []}
        print(json.dumps(data, indent=2))
    elif args.registry == "agent":
        p = root / "registry" / "agent_registry.json"
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"agents": []}
        print(json.dumps(data, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
