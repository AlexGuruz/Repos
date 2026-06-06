from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.bank_vendor_cleaner.vendor_lookup import (
    _normalize_lookup_query,
    lookup_vendor,
    should_trigger_lookup,
)
from brain.bank_vendor_cleaner.paths import default_vendor_lookup_cache_path


def _vectors() -> dict:
    p = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "bank_vendor_cleaner"
        / "vendor_lookup_test_vectors.json"
    )
    return json.loads(p.read_text(encoding="utf-8"))


def test_config_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    for rel in (
        "config/bank_vendor_cleaner/vendor_lookup_rules.yaml",
        "config/bank_vendor_cleaner/vendor_lookup_cache.yaml",
        "config/bank_vendor_cleaner/vendor_lookup_providers.yaml",
        "config/bank_vendor_cleaner/vendor_lookup_settings.example.env",
        "scripts/vendor_lookup_worker.py",
        "runbooks/bank_vendor_cleaner_vendor_lookup.md",
    ):
        assert (root / rel).is_file(), rel


def test_trigger_rules_from_fixtures() -> None:
    for case in _vectors().get("cases", []):
        triggered = should_trigger_lookup(
            case["raw_input"],
            case.get("deterministic_label", ""),
            case.get("label_source", "fallback"),
        )
        assert triggered == case["expect_trigger"], case["id"]


def test_lookup_decisions_no_sheet_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VENDOR_LOOKUP_CACHE_PATH", str(tmp_path / "cache.yaml"))
    tmp_path.joinpath("cache.yaml").write_text(
        "version: 1\nentries: []\npending: []\n",
        encoding="utf-8",
    )

    def _fake_search(*_a, **_k):
        return []

    for case in _vectors().get("cases", []):
        result = lookup_vendor(
            case["raw_input"],
            deterministic_label=case.get("deterministic_label", ""),
            deterministic_location=case.get("deterministic_location", ""),
            city_hint=case.get("city_hint", ""),
            state_hint=case.get("state_hint", ""),
            label_source=case.get("label_source"),
            search_fn=_fake_search,
            write_pending=False,
        )
        if "expect_decision" in case:
            assert result.decision == case["expect_decision"], case["id"]
        if case.get("expect_no_sheet_write"):
            assert result.decision in {"manual_review", "reject", "cache_candidate"}


def test_local_cache_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = {
        "version": 1,
        "entries": [
            {
                "raw_pattern": "kraken 8888378818 *n tx",
                "canonical_label": "Kraken",
                "city": "",
                "state": "TX",
                "confidence": "high",
                "approved": True,
            }
        ],
        "pending": [],
    }

    result = lookup_vendor(
        "kraken 8888378818 *n tx",
        deterministic_label="Kraken",
        label_source="rule",
        cache=cache,
        write_pending=False,
    )
    assert result.decision == "reject"


def test_pending_cache_match_unknown() -> None:
    cache = {
        "version": 1,
        "entries": [],
        "pending": [
            {
                "raw_pattern": "abc*p 07320 pf terre 812-235-5001 in 05/29",
                "candidate_label": "ABC Store",
                "candidate_city": "Terre Haute",
                "candidate_state": "IN",
                "confidence": "low",
                "approved": False,
            }
        ],
    }
    result = lookup_vendor(
        "abc*p 07320 pf terre 812-235-5001 in 05/29",
        deterministic_label="Abc*p Pf Terre",
        label_source="fallback",
        cache=cache,
        write_pending=False,
    )
    assert result.candidate_label == "ABC Store"
    assert result.decision == "manual_review"


def test_processor_query_cleanup() -> None:
    for case in _vectors().get("processor_cleanup", []):
        q = _normalize_lookup_query(case["raw_input"])
        for bad in case.get("normalized_query_should_not_contain", []):
            assert bad.lower() not in q.lower(), case["id"]


def test_default_cache_file_loads() -> None:
    assert default_vendor_lookup_cache_path().is_file()
