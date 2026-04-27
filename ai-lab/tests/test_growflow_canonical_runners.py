from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.integration_inventory.growflow_classify import (
    PREPARED_CONTEXT_FEEDER_NAMES,
    UNSAFE_WITHOUT_METADATA_NAMES,
    build_inventory,
)

_AI_LAB = Path(__file__).resolve().parents[1]
_JSON = _AI_LAB / "state" / "integration_inventory" / "growflow_runners.json"


def _load_inventory() -> dict:
    assert _JSON.is_file(), f"missing {_JSON} — run: python scripts/generate_growflow_runners_json.py"
    return json.loads(_JSON.read_text(encoding="utf-8"))


def test_growflow_runners_json_schema_and_nonempty() -> None:
    inv = _load_inventory()
    assert inv.get("version") == 1
    scripts = inv["scripts"]
    assert isinstance(scripts, list) and len(scripts) >= 10
    counts = inv.get("counts") or {}
    assert sum(counts.get(k, 0) for k in inv["classification_labels"]) == len(scripts)
    assert counts.get("prepared_context_feeders", 0) == sum(
        1 for r in scripts if r.get("prepared_context_source")
    )


def test_inventory_matches_live_classifier() -> None:
    """Committed JSON stays in sync with heuristic rules (regenerate script if this fails)."""
    growflow = _AI_LAB.parent / "Growflow"
    if not growflow.is_dir():
        pytest.skip("Growflow sibling repo not present")
    live = build_inventory(growflow)
    disk = _load_inventory()
    assert len(live["scripts"]) == len(disk["scripts"])
    live_by_rel = {r["relative"]: r for r in live["scripts"]}
    for row in disk["scripts"]:
        assert live_by_rel[row["relative"]] == row


def test_probe_and_deprecated_never_canonical() -> None:
    inv = _load_inventory()
    bad: list[str] = []
    for r in inv["scripts"]:
        rel = (r.get("relative") or "").lower()
        name = Path(rel).name
        cat = r.get("category")
        if cat == "canonical_runner":
            if "_probe" in rel or name.startswith("probe_"):
                bad.append(f"probe-like canonical: {rel}")
            if name.startswith("_tmp") or name.startswith("_test"):
                bad.append(f"temp-like canonical: {rel}")
            if name in ("_patch_ac10.py", "_patch_iferror_test.py", "_sellout_final.py"):
                bad.append(f"deprecated-name canonical: {rel}")
    assert not bad, "; ".join(bad)


def test_unsafe_and_writeish_candidates_require_approval_flag() -> None:
    inv = _load_inventory()
    for r in inv["scripts"]:
        rel = r.get("relative") or ""
        name = Path(rel).name
        if r.get("category") == "unsafe_without_approval_metadata":
            assert r.get("approval_required_for_tool_registry") is True, rel
        if name in UNSAFE_WITHOUT_METADATA_NAMES:
            assert r.get("approval_required_for_tool_registry") is True, rel


def test_prepared_context_feeders_flag_consistent() -> None:
    inv = _load_inventory()
    for r in inv["scripts"]:
        name = Path(r.get("relative") or "").name
        flag = bool(r.get("prepared_context_source"))
        assert flag == (name in PREPARED_CONTEXT_FEEDER_NAMES), name


def test_registry_growflow_tool_is_read_only_not_approval_forced() -> None:
    """Sanity: only known Growflow registry entry remains read-biased (no new unsafe registration)."""
    reg = json.loads((_AI_LAB / "registry" / "scripts.json").read_text(encoding="utf-8"))
    gf = [x for x in reg if "growflow" in (x.get("tool_name") or "").lower()]
    assert gf, "expected at least one growflow* tool in registry/scripts.json"
    for x in gf:
        assert x.get("tool_name") == "growflow_sales_today"
        assert "ingest" not in (x.get("path") or "").lower()
