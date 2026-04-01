"""
Secret broker (PDR Phase 3). Fetches credentials; never exposes secrets to LLM; enforces scope.
Backends: Google Secret Manager, local encrypted vault. Stub implementation.
"""
from __future__ import annotations

import os
from typing import Any


def get_secret(ref: str) -> str | None:
    """
    Resolve a secret reference to its value. Ref can be env var name or a path (e.g. gcp:project/secret).
    Stub: loads from env only. Never log or return secrets to the LLM context.
    """
    env_key = ref.upper().replace(".", "_").replace("/", "_")
    val = os.environ.get(env_key)
    if val is not None:
        return val
    return None


def get_secret_scope(connector: str) -> list[str]:
    """Return allowed scope for a connector (from config). Stub returns empty."""
    _ = connector
    return []
