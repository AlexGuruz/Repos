from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.integration_inventory.integration_inventory_generator import generate_integration_inventory

_AI_LAB = Path(__file__).resolve().parents[1]

REQUIRED_SCRIPT_KEYS = frozenset(
    {
        "path",
        "name",
        "extension",
        "guessed_purpose",
        "classification",
        "imported_by_or_referenced_by",
        "scheduled_by",
        "registered_tool_name",
        "prepared_context_source",
        "writes_state_guess",
        "external_side_effect_guess",
        "approval_required_guess",
        "status",
        "reasons",
    }
)
REQUIRED_TOOL_KEYS = frozenset(
    {
        "tool_name",
        "source",
        "implementation_path",
        "exists",
        "action_type",
        "read_only",
        "approval_required",
        "allowlist_eligible",
        "metadata_complete",
        "risks",
    }
)


@pytest.fixture(scope="module")
def inv_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("integration_inventory")
    doc = out / "SCRIPT_TOOL_INVENTORY_AUTO.md"
    generate_integration_inventory(ai_lab=_AI_LAB, output_dir=out, docs_path=doc)
    return out


def test_generator_writes_all_required_files(inv_dir: Path) -> None:
    for name in ("scripts.json", "tools.json", "triggers.json", "orphans.json", "summary.json"):
        assert (inv_dir / name).is_file(), f"missing {name}"
    doc = inv_dir / "SCRIPT_TOOL_INVENTORY_AUTO.md"
    assert doc.is_file() and doc.stat().st_size > 50


def test_stable_top_level_schema(inv_dir: Path) -> None:
    scripts = json.loads((inv_dir / "scripts.json").read_text(encoding="utf-8"))
    assert scripts.get("schema_version") == 1
    assert "generated_at" in scripts and isinstance(scripts["generated_at"], str)
    assert isinstance(scripts.get("scripts"), list) and scripts["scripts"]
    row = scripts["scripts"][0]
    assert REQUIRED_SCRIPT_KEYS == frozenset(row.keys())

    tools = json.loads((inv_dir / "tools.json").read_text(encoding="utf-8"))
    assert tools.get("schema_version") == 1
    assert REQUIRED_TOOL_KEYS <= frozenset(tools["tools"][0].keys())

    trig = json.loads((inv_dir / "triggers.json").read_text(encoding="utf-8"))
    assert trig.get("schema_version") == 1 and isinstance(trig.get("triggers"), list)

    orphans = json.loads((inv_dir / "orphans.json").read_text(encoding="utf-8"))
    assert orphans.get("schema_version") == 1 and isinstance(orphans.get("orphans"), list)

    summary = json.loads((inv_dir / "summary.json").read_text(encoding="utf-8"))
    for k in (
        "total_scripts_scanned",
        "total_tools",
        "total_triggers",
        "orphan_candidates",
        "top_10_highest_priority_cleanup_items",
    ):
        assert k in summary


def test_registry_ai_lab_paths_exist_or_marked(inv_dir: Path) -> None:
    tools = json.loads((inv_dir / "tools.json").read_text(encoding="utf-8"))["tools"]
    for t in tools:
        if t.get("source") != "registry/scripts.json":
            continue
        impl = t.get("implementation_path")
        if not impl or not isinstance(impl, str):
            continue
        reg = json.loads((_AI_LAB / "registry" / "scripts.json").read_text(encoding="utf-8"))
        match = next((r for r in reg if r.get("tool_name") == t.get("tool_name")), None)
        if not match or match.get("repo") != "ai-lab":
            continue
        assert t.get("exists") is True, f"missing on disk: {impl}"


def test_write_heuristic_cli_not_false_safe(inv_dir: Path) -> None:
    scripts = json.loads((inv_dir / "scripts.json").read_text(encoding="utf-8"))["scripts"]
    bad = [
        s
        for s in scripts
        if s.get("classification") == "cli_script"
        and s.get("writes_state_guess")
        and s.get("external_side_effect_guess")
        and not s.get("approval_required_guess")
    ]
    assert not bad, bad[:3]


def test_probe_diagnostic_not_promoted_to_registry(inv_dir: Path) -> None:
    scripts = json.loads((inv_dir / "scripts.json").read_text(encoding="utf-8"))["scripts"]
    for s in scripts:
        if s.get("classification") not in ("temp_probe", "diagnostic"):
            continue
        assert s.get("registered_tool_name") is None, s.get("path")
        assert s.get("status") == "manual_only"


def test_growflow_merged_when_inventory_present(inv_dir: Path) -> None:
    gf = _AI_LAB / "state" / "integration_inventory" / "growflow_runners.json"
    if not gf.is_file():
        pytest.skip("growflow_runners.json not committed")
    scripts = json.loads((inv_dir / "scripts.json").read_text(encoding="utf-8"))["scripts"]
    gf_rows = [s for s in scripts if str(s.get("path", "")).startswith("../Growflow/")]
    assert len(gf_rows) >= 5


def test_committed_state_has_schema(inv_dir: Path) -> None:
    """Committed artifacts under state/ should stay parseable after merges."""
    p = _AI_LAB / "state" / "integration_inventory" / "scripts.json"
    if not p.is_file():
        pytest.skip("committed scripts.json not present")
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    assert len(data.get("scripts") or []) == len(
        json.loads((inv_dir / "scripts.json").read_text(encoding="utf-8")).get("scripts") or []
    )
