#!/usr/bin/env python3
"""
Regenerate registry/README_catalog.md from components.yaml and environments.yaml.
Deterministic output; run after catalog edits. Requires PyYAML.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML required.", file=sys.stderr)
    sys.exit(2)


def _root() -> Path:
    r = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if r:
        return Path(r)
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = _root()
    comp_path = root / "registry" / "components.yaml"
    env_path = root / "registry" / "environments.yaml"
    out_path = root / "registry" / "README_catalog.md"

    with comp_path.open(encoding="utf-8") as f:
        comp_doc = yaml.safe_load(f)
    with env_path.open(encoding="utf-8") as f:
        env_doc = yaml.safe_load(f)

    lines: list[str] = [
        "# System catalog (generated)",
        "",
        "Do not edit by hand. Regenerate with:",
        "",
        "```bash",
        "pip install -r scripts/requirements-catalog.txt",
        "python scripts/generate_catalog_doc.py",
        "```",
        "",
        "Specification: [CATALOG_SSOT_IMPLEMENTATION_PLAN.md](../CATALOG_SSOT_IMPLEMENTATION_PLAN.md).",
        "",
        "## Environments",
        "",
        "| id | runtime_class | purpose |",
        "|----|---------------|---------|",
    ]
    for e in env_doc.get("environments") or []:
        lines.append(
            f"| {e.get('id','')} | {e.get('runtime_class','')} | {e.get('purpose','')[:80]} |"
        )

    lines.extend(
        [
            "",
            "## Components",
            "",
            "| id | type | lifecycle | primary_repo | code_owner |",
            "|----|------|-----------|--------------|------------|",
        ]
    )
    for c in comp_doc.get("components") or []:
        lines.append(
            f"| {c.get('id','')} | {c.get('component_type','')} | {c.get('lifecycle_state','')} "
            f"| {c.get('primary_repo','')} | {c.get('code_owner','')} |"
        )

    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print("Wrote", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
