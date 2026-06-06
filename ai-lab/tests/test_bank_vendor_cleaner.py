from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.bank_vendor_cleaner.engine import (
    build_alias_lookup,
    process_transaction,
)
from brain.bank_vendor_cleaner.loader import load_alias_map, load_cleaning_rules
from brain.bank_vendor_cleaner.paths import default_test_vectors_path


def _vectors() -> dict:
    return json.loads(default_test_vectors_path().read_text(encoding="utf-8"))


@pytest.fixture
def alias_map() -> dict:
    return load_alias_map()


@pytest.fixture
def cleaning_rules() -> dict:
    return load_cleaning_rules()


@pytest.fixture
def lookups(alias_map: dict):
    return build_alias_lookup(alias_map)


def test_all_export_vectors(alias_map: dict, cleaning_rules: dict, lookups) -> None:
    by_raw, by_canonical = lookups
    failures: list[str] = []
    for case in _vectors().get("cases", []):
        raw = case["input_column_c"]
        got = process_transaction(raw, by_raw, by_canonical, cleaning_rules=cleaning_rules)
        if got.label != case["expected_column_c"]:
            failures.append(
                f"{case['id']} label: got {got.label!r} expected {case['expected_column_c']!r}"
            )
        if got.location != case["expected_column_d"]:
            failures.append(
                f"{case['id']} location: got {got.location!r} expected {case['expected_column_d']!r}"
            )
    assert not failures, "\n".join(failures)


def test_edge_cases(alias_map: dict, cleaning_rules: dict, lookups) -> None:
    by_raw, by_canonical = lookups
    for case in _vectors().get("edge_cases", []):
        if "expected_column_c" not in case:
            continue
        got = process_transaction(
            case["input_column_c"],
            by_raw,
            by_canonical,
            cleaning_rules=cleaning_rules,
        )
        assert got.label == case["expected_column_c"], case["id"]
        assert got.location == case.get("expected_column_d", ""), case["id"]


def test_manifest_and_config_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in (
        "config/bank_vendor_cleaner/README.md",
        "config/bank_vendor_cleaner/agent_manifest.json",
        "config/bank_vendor_cleaner/memory_alias_map.yaml",
        "config/bank_vendor_cleaner/cleaning_rules.yaml",
        "scripts/sheet_label_pipeline.py",
        "runbooks/bank_vendor_cleaner_pipeline_spec.md",
        "docs/bank_vendor_cleaner/AGENT_INSTRUCTIONS.md",
        "config/bank_vendor_cleaner/settings.example.env",
        "reports/.gitkeep",
    ):
        assert (root / rel).is_file(), rel
