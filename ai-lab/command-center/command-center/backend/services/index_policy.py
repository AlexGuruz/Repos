from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.ai_lab import AI_LAB_ROOT


# command-center app root: .../command-center/command-center
APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = APP_ROOT / "config" / "index_policy.yaml"


@dataclass(frozen=True)
class IndexPolicyIdentity:
    embedding_model_id: str
    embedding_model_revision: str
    policy_hash: str
    metadata_schema_version: int
    index_schema_version: int
    collection_layout_version: int
    chunk_identity_version: int
    parser_version: int


def _stable_json(obj: Any) -> str:
    """
    Deterministic serialization for hashing.
    Uses sorted keys + compact separators to avoid whitespace drift.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_lists_recursively(v: Any) -> Any:
    """
    Normalize list ordering to make policy_hash stable even if YAML list order changes.
    """
    if isinstance(v, list):
        # Best-effort sort; if elements are mixed types, keep original order.
        try:
            return sorted((_sort_lists_recursively(x) for x in v), key=lambda x: str(x))
        except TypeError:
            return [_sort_lists_recursively(x) for x in v]
    if isinstance(v, dict):
        return {k: _sort_lists_recursively(val) for k, val in v.items()}
    return v


def normalize_policy(policy_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize the policy manifest into a canonical dict used for policy_hash + identity.
    """
    # Copy + only keep fields we consider authoritative identity/policy.
    normalized = {
        "embedding_model_id": str(policy_dict["embedding_model_id"]),
        "embedding_model_revision": str(policy_dict.get("embedding_model_revision", "")),
        "embedding_dimensions": int(policy_dict["embedding_dimensions"]),
        "chunking_strategy": str(policy_dict["chunking_strategy"]),
        "chunk_size": int(policy_dict["chunk_size"]),
        "chunk_overlap": int(policy_dict["chunk_overlap"]),
        "file_type_rules": {
            "include_extensions": list(policy_dict["file_type_rules"]["include_extensions"]),
            "ignore_paths": list(policy_dict["file_type_rules"]["ignore_paths"]),
        },
        "metadata_schema_version": int(policy_dict["metadata_schema_version"]),
        "index_schema_version": int(policy_dict["index_schema_version"]),
        "collection_layout_version": int(policy_dict["collection_layout_version"]),
        "chunk_identity_version": int(policy_dict["chunk_identity_version"]),
        "parser_version": int(policy_dict["parser_version"]),
        "rerank_strategy": str(policy_dict.get("rerank_strategy", "none")),
    }
    return _sort_lists_recursively(normalized)


def resolve_index_policy_path(policy_path: str | Path | None = None) -> Path:
    """
    Absolute path to the policy YAML on disk.
    """
    path = Path(policy_path) if policy_path else DEFAULT_POLICY_PATH
    if not path.is_absolute():
        path = APP_ROOT / path
    return path


def compute_policy_hash_file(policy_path: Path) -> str:
    """
    Must match worker_assistant: sha256: + hex digest of raw file bytes (UTF-8 file as stored).
    Copy the same YAML bytes to hub + worker so policy_hash_used validates.
    """
    digest = hashlib.sha256(policy_path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def compute_policy_hash_normalized(policy_dict: dict[str, Any]) -> str:
    """
    Legacy semantic hash (normalized JSON). Prefer compute_policy_hash_file for worker contract.
    """
    normalized = normalize_policy(policy_dict)
    digest = hashlib.sha256(_stable_json(normalized).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_index_policy(policy_path: str | Path | None = None) -> dict[str, Any]:
    """
    Load the authoritative index policy manifest from hub config.
    """
    path = resolve_index_policy_path(policy_path)
    if not path.exists():
        raise FileNotFoundError(f"Index policy manifest not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or "embedding_model_id" not in data:
        raise ValueError(f"Invalid index policy manifest: {path}")
    return data


def get_expected_policy_identity(
    policy_dict: dict[str, Any] | None = None,
    policy_path: str | Path | None = None,
) -> IndexPolicyIdentity:
    """
    Produce the minimal identity fields the coordinator uses for strict Gate C validation.
    policy_hash is the raw-file SHA-256 (worker contract).
    """
    resolved = resolve_index_policy_path(policy_path)
    policy_dict = policy_dict or load_index_policy(resolved)
    normalized = normalize_policy(policy_dict)
    return IndexPolicyIdentity(
        embedding_model_id=normalized["embedding_model_id"],
        embedding_model_revision=normalized["embedding_model_revision"],
        policy_hash=compute_policy_hash_file(resolved),
        metadata_schema_version=normalized["metadata_schema_version"],
        index_schema_version=normalized["index_schema_version"],
        collection_layout_version=normalized["collection_layout_version"],
        chunk_identity_version=normalized["chunk_identity_version"],
        parser_version=normalized["parser_version"],
    )


def get_expected_policy(policy_dict: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Return the normalized full authoritative policy dict (useful for validation diffs/debugging).
    """
    policy_dict = policy_dict or load_index_policy()
    return normalize_policy(policy_dict)

