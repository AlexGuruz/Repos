from __future__ import annotations

import time
from pathlib import Path

import pytest

from brain.repo_doc_validation import validate_readme, validate_runbook, validate_system_map
from brain.repo_docs_maintainer import (
    build_docs_cleanup_plan,
    create_docs_update_proposal,
)
from brain.prepared_context.builders import build_repo_pulse
from brain.prepared_context.store import write_snapshot


def _valid_readme() -> str:
    return """# Demo Service

This service processes widgets for internal teams and exposes a small HTTP API.

## Overview

The demo service is stateless and reads configuration from the environment.

## Setup / installation

Clone the repo and install dependencies.

```bash
npm install
```

## Configuration / environment variables

Set `PORT` and `DATABASE_URL` before starting.

## Usage / entrypoints

Run the API locally:

```bash
npm start
```

## Architecture or system overview

Node HTTP server, worker queue consumer, Postgres for durable state.

## Verification / how to confirm working

```bash
npm test
```

Expect all tests green and `/health` returns 200.
"""


def test_readme_validation_detects_missing_sections(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text("# X\n\n## Overview\n\nShort text here only.\n", encoding="utf-8")
    r = validate_readme(p)
    assert r["is_valid"] is False
    assert "setup" in r["missing_sections"]
    assert "configuration" in r["missing_sections"]


def test_valid_readme_passes_validation(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text(_valid_readme(), encoding="utf-8")
    r = validate_readme(p)
    assert r["is_valid"] is True
    assert r["missing_sections"] == []
    assert r["weak_sections"] == []


def test_weak_empty_section_flagged(tmp_path: Path) -> None:
    body = _valid_readme()
    # Replace verification with thin content (other sections keep commands)
    body = body.split("## Verification")[0] + "## Verification\n\nshort\n"
    p = tmp_path / "README.md"
    p.write_text(body, encoding="utf-8")
    r = validate_readme(p)
    assert r["is_valid"] is False
    assert "verification" in r["weak_sections"]


def test_no_actionable_command_weak(tmp_path: Path) -> None:
    lines = []
    for line in _valid_readme().splitlines():
        if any(x in line.lower() for x in ("```", "npm ", "pip ", "python ", "./")):
            continue
        lines.append(line)
    text = "\n".join(lines)
    p = tmp_path / "README.md"
    p.write_text(text, encoding="utf-8")
    r = validate_readme(p)
    assert "no_actionable_command" in r["weak_sections"]


def test_cleanup_plan_includes_validation_results() -> None:
    write_snapshot(build_repo_pulse())
    plan = build_docs_cleanup_plan(message="plan", max_items=10)
    assert "readme_validations" in plan
    assert isinstance(plan["readme_validations"], list)
    for item in plan.get("plan_items") or []:
        assert "readme_validation" in item
        assert "priority_score" in item


def test_proposal_includes_missing_section_structure() -> None:
    write_snapshot(build_repo_pulse())
    prop = create_docs_update_proposal(message="proposal")
    assert prop.get("approval_required") is True
    assert "missing_sections" in prop
    assert "proposed_sections" in prop
    assert isinstance(prop["proposed_sections"], list)
    if prop.get("target_file") and prop.get("readme_validation"):
        for sec in prop["proposed_sections"]:
            assert "name" in sec
            assert "outline" in sec


def test_validators_do_not_write_files(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text("# A\n\n## Overview\n\n" + ("x" * 50), encoding="utf-8")
    before = p.read_bytes()
    _ = validate_readme(p)
    assert p.read_bytes() == before
    rb = tmp_path / "runbook.md"
    rb.write_text(
        "## Purpose\n\n" + ("p" * 50) + "\n## Steps\n\n`./run.sh`\n"
        "## Expected result\n\n" + ("e" * 50) + "\n## Failure handling\n\n" + ("f" * 50),
        encoding="utf-8",
    )
    b2 = rb.read_bytes()
    _ = validate_runbook(rb)
    assert rb.read_bytes() == b2


def test_runbook_and_system_map_policies(tmp_path: Path) -> None:
    rb = tmp_path / "rb.md"
    rb.write_text(
        "## Purpose\n\n" + ("a" * 50) + "\n## Steps\n\nDo the following:\n\n```bash\necho hi\n```\n"
        + ("s" * 45)
        + "\n## Expected result\n\n"
        + ("b" * 50)
        + "\n## Failure handling\n\n"
        + ("c" * 50),
        encoding="utf-8",
    )
    assert validate_runbook(rb)["is_valid"] is True
    sm = tmp_path / "map.md"
    sm.write_text(
        "## Components\n\n" + ("c" * 50) + "\n## Data flow\n\n" + ("d" * 50) + "\n## Integration\n\n" + ("i" * 50),
        encoding="utf-8",
    )
    assert validate_system_map(sm)["is_valid"] is True


def test_validation_timing_single_readme(tmp_path: Path) -> None:
    p = tmp_path / "README.md"
    p.write_text(_valid_readme(), encoding="utf-8")
    t0 = time.perf_counter()
    for _ in range(20):
        validate_readme(p)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 20
    assert elapsed_ms < 300.0, f"mean validate_readme too slow: {elapsed_ms:.1f}ms"
