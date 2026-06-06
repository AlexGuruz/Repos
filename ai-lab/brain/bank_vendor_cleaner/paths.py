from __future__ import annotations

from pathlib import Path

_AI_LAB_ROOT = Path(__file__).resolve().parents[2]


def ai_lab_root() -> Path:
    return _AI_LAB_ROOT


def config_dir() -> Path:
    return _AI_LAB_ROOT / "config" / "bank_vendor_cleaner"


def docs_dir() -> Path:
    return _AI_LAB_ROOT / "docs" / "bank_vendor_cleaner"


def default_alias_map_path() -> Path:
    return config_dir() / "memory_alias_map.yaml"


def default_cleaning_rules_path() -> Path:
    return config_dir() / "cleaning_rules.yaml"


def default_manifest_path() -> Path:
    return config_dir() / "agent_manifest.json"


def default_overrides_path() -> Path:
    return config_dir() / "known_city_state_overrides.yaml"


def default_rejected_aliases_path() -> Path:
    return config_dir() / "rejected_aliases.yaml"


def agent_instructions_path() -> Path:
    return docs_dir() / "AGENT_INSTRUCTIONS.md"


def pipeline_spec_path() -> Path:
    return _AI_LAB_ROOT / "runbooks" / "bank_vendor_cleaner_pipeline_spec.md"


def default_test_vectors_path() -> Path:
    return _AI_LAB_ROOT / "tests" / "fixtures" / "bank_vendor_cleaner" / "test_vectors.json"


def vendor_lookup_test_vectors_path() -> Path:
    return _AI_LAB_ROOT / "tests" / "fixtures" / "bank_vendor_cleaner" / "vendor_lookup_test_vectors.json"


def reports_dir() -> Path:
    return _AI_LAB_ROOT / "reports"


def default_vendor_lookup_rules_path() -> Path:
    return config_dir() / "vendor_lookup_rules.yaml"


def default_vendor_lookup_cache_path() -> Path:
    return config_dir() / "vendor_lookup_cache.yaml"


def default_vendor_lookup_providers_path() -> Path:
    return config_dir() / "vendor_lookup_providers.yaml"


def vendor_lookup_review_queue_path() -> Path:
    return reports_dir() / "vendor_lookup_review_queue.json"
