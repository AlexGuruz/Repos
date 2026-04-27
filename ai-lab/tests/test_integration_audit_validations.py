from __future__ import annotations

import json
from pathlib import Path

from brain.prepared_context import builders
from brain.prepared_context.loader import load_snapshot_fresh
from brain.prepared_context.store import write_snapshot
from brain.tool_registry import load_tool_registry


ROOT = Path(__file__).resolve().parents[1]


def test_registry_scripts_resolve_to_existing_paths() -> None:
    scripts_path = ROOT / "registry" / "scripts.json"
    data = json.loads(scripts_path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and data
    local_checked = 0
    for row in data:
        repo = (row.get("repo") or "").strip()
        rel = (row.get("path") or "").strip()
        assert rel, f"missing path in registry row: {row}"
        if repo:
            resolved = (ROOT.parent / repo / rel).resolve()
        else:
            resolved = (ROOT / rel).resolve()
        if repo.lower() in {"", "ai-lab"}:
            local_checked += 1
            assert resolved.exists(), f"missing local tool target path: {resolved}"
    assert local_checked > 0


def test_scheduler_setup_scripts_exist() -> None:
    required = [
        ROOT / "scripts" / "setup_prepared_context_tasks.ps1",
        ROOT / "scripts" / "remove_prepared_context_tasks.ps1",
        ROOT / "scripts" / "setup_worker_tunnel_task.ps1",
        ROOT / "scripts" / "maintain_worker_tunnel.ps1",
    ]
    for path in required:
        assert path.exists(), f"missing scheduler script: {path}"


def test_prepared_snapshot_can_be_built_persisted_and_loaded() -> None:
    snap = builders.build_snapshot("system_snapshot")
    out = write_snapshot(snap)
    assert out.exists()
    loaded = load_snapshot_fresh("system_snapshot")
    assert loaded is not None
    assert loaded.get("snapshot_type") == "system_snapshot"
    assert "generated_at" in loaded


def test_tool_registry_has_approval_metadata_for_each_tool() -> None:
    rows = load_tool_registry()
    assert rows
    for row in rows:
        assert "name" in row and row["name"]
        assert "approval_required" in row
        assert "side_effects" in row


def test_audit_docs_exist() -> None:
    required_docs = [
        ROOT / "docs" / "SYSTEM_WIRING_AUDIT.md",
        ROOT / "docs" / "SCRIPT_TOOL_INVENTORY.md",
        ROOT / "docs" / "TOOL_REGISTRY_AUDIT.md",
        ROOT / "docs" / "ORPHANED_SCRIPT_REPORT.md",
        ROOT / "docs" / "TRIGGER_AND_SCHEDULER_AUDIT.md",
        ROOT / "docs" / "PREPARED_CONTEXT_WIRING_AUDIT.md",
        ROOT / "docs" / "WORKER_INTEGRATION_AUDIT.md",
        ROOT / "docs" / "GOAL_ALIGNMENT_AUDIT.md",
        ROOT / "docs" / "AI_LAB_INTEGRATION_HEALTH_SUMMARY.md",
    ]
    for doc in required_docs:
        assert doc.exists(), f"missing audit doc: {doc}"

