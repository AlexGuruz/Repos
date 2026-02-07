"""
Persistent state helpers for incremental Sheets posting.

The state file is stored at `.kylo/state.json` by default.  It keeps per-company
signatures for projected cells so we can skip posting unchanged values.  The
format is intentionally simple JSON to make manual inspection easy.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Set

from services.common.instance import (
    get_instance_id,
    default_posting_state_path,
    legacy_posting_state_path,
    migrate_legacy_file,
)


STATE_VERSION = 1
LOCK_TIMEOUT_SECONDS = 10


@dataclass
class State:
    version: int = STATE_VERSION
    cell_signatures: Dict[str, Dict[str, str]] = field(default_factory=dict)
    processed_txn_uids: Dict[str, Set[str]] = field(default_factory=dict)
    skipped_txn_uids: Dict[str, Set[str]] = field(default_factory=dict)

    def get_signature(self, company_id: str, cell_key: str) -> Optional[str]:
        return self.cell_signatures.get(company_id, {}).get(cell_key)

    def set_signature(self, company_id: str, cell_key: str, signature: str) -> None:
        self.cell_signatures.setdefault(company_id, {})[cell_key] = signature

    def merge_processed(self, company_id: str, txn_uids: Iterable[str]) -> None:
        if not txn_uids:
            return
        bucket = self.processed_txn_uids.setdefault(company_id, set())
        bucket.update(txn_uids)
        # Remove from skipped when successfully processed
        if company_id in self.skipped_txn_uids:
            self.skipped_txn_uids[company_id].difference_update(txn_uids)

    def add_skipped(self, company_id: str, txn_uids: Iterable[str]) -> None:
        """Track transaction UIDs that were skipped due to missing rules."""
        if not txn_uids:
            return
        bucket = self.skipped_txn_uids.setdefault(company_id, set())
        bucket.update(txn_uids)

    def get_skipped(self, company_id: str) -> Set[str]:
        """Get set of skipped transaction UIDs for a company."""
        return self.skipped_txn_uids.get(company_id, set()).copy()

    def clear_skipped(self, company_id: str) -> None:
        """Clear skipped transactions for a company (e.g., when rules change)."""
        self.skipped_txn_uids.pop(company_id, None)

    def to_serializable(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "cell_signatures": self.cell_signatures,
            "processed_txn_uids": {k: sorted(v) for k, v in self.processed_txn_uids.items()},
            "skipped_txn_uids": {k: sorted(v) for k, v in self.skipped_txn_uids.items()},
        }


class StateError(RuntimeError):
    """Raised when state cannot be loaded or written safely."""


def _default_state_path() -> Path:
    """Resolve the default posting state path.

    Precedence:
      1) KYLO_STATE_PATH (explicit override)
      2) KYLO_INSTANCE_ID -> .kylo/instances/<instance_id>/state/posting_state.json
      3) .kylo/state.json
    """
    env_path = (os.environ.get("KYLO_STATE_PATH") or "").strip()
    if env_path:
        return Path(env_path).resolve()
    # Ensure we get instance ID from environment (should be set by start script)
    iid = get_instance_id()
    if not iid:
        # Fallback: try to get from environment directly
        iid = (os.environ.get("KYLO_INSTANCE_ID") or "").strip() or None
    if iid:
        new_path = default_posting_state_path(iid).resolve()
        legacy_path = legacy_posting_state_path(iid).resolve()
        migrate_legacy_file(legacy_path=legacy_path, new_path=new_path)
        # Also migrate any old post_state_<year>.json files
        legacy_year_path = Path(".kylo") / f"post_state_{iid.split('_')[-1]}.json"
        if legacy_year_path.exists() and legacy_year_path != legacy_path:
            migrate_legacy_file(legacy_path=legacy_year_path, new_path=new_path)
        return new_path
    return Path(".kylo/state.json").resolve()


@contextmanager
def _acquire_lock(lock_path: Path):
    """Acquire an exclusive filesystem lock using an adjacent .lock file."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + LOCK_TIMEOUT_SECONDS
    lock_file = lock_path
    while True:
        try:
            fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            break
        except FileExistsError:
            if time.time() > deadline:
                raise StateError(f"Timed out waiting for state lock {lock_file}")
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            os.close(fd)  # type: ignore[name-defined]
        except Exception:
            pass
        try:
            os.remove(lock_file)
        except FileNotFoundError:
            pass


def load_state(path: Optional[Path] = None) -> State:
    path = path or _default_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return State()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - catastrophic state
        raise StateError(f"State file {path} is not valid JSON: {exc}") from exc
    version = data.get("version", STATE_VERSION)
    if version != STATE_VERSION:
        raise StateError(f"Unsupported state version {version}; expected {STATE_VERSION}")
    cell_signatures = data.get("cell_signatures") or {}
    processed = data.get("processed_txn_uids") or {}
    skipped = data.get("skipped_txn_uids") or {}
    # Convert processed lists to sets for faster merging
    processed_sets = {k: set(v) for k, v in processed.items()}
    skipped_sets = {k: set(v) for k, v in skipped.items()}
    state = State(
        version=version,
        cell_signatures={
            company: {str(key): str(sig) for key, sig in (values or {}).items()}
            for company, values in cell_signatures.items()
        },
        processed_txn_uids=processed_sets,
        skipped_txn_uids=skipped_sets,
    )
    return state


def save_state(state: State, path: Optional[Path] = None) -> None:
    path = path or _default_state_path()
    lock_path = path.with_suffix(path.suffix + ".lock")
    with _acquire_lock(lock_path):
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload = json.dumps(state.to_serializable(), indent=2, sort_keys=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(tmp_path, path)


def compute_cell_key(tab: str, header: str, date_key: str, *, spreadsheet_id: str | None = None) -> str:
    """Return a stable key for a projected cell.

    Historically this was just (tab/header/date). When routing across multiple
    spreadsheets (e.g., year-based workbook routing), we include spreadsheet_id
    to avoid cross-workbook signature collisions.
    """

    parts = [
        (tab or "").strip(),
        (header or "").strip(),
        (date_key or "").strip(),
    ]
    if spreadsheet_id:
        parts.insert(0, (spreadsheet_id or "").strip())
    return "|".join(parts).upper()


def compute_signature(txn_uids: Iterable[str], total_cents: int) -> str:
    """Return a SHA-256 signature for the contributing transactions."""

    import hashlib

    normalized = sorted(str(uid) for uid in txn_uids if uid)
    payload = "|".join(normalized) + f"|{total_cents}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "State",
    "StateError",
    "compute_cell_key",
    "compute_signature",
    "load_state",
    "save_state",
]


