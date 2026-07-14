"""Job manifest + vault Job primer loader."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import paths as pathmod
from .errors import JOB_NOT_FOUND, OPERATOR_CONFIG_INVALID, OperatorError
from .models import JobPrimerBundle
from .settings import get_settings


@dataclass(frozen=True)
class JobManifestEntry:
    job_id: str
    title: str
    note: str
    intent_keys: tuple[str, ...]
    tool_ids: tuple[str, ...]


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml  # type: ignore

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise OperatorError(OPERATOR_CONFIG_INVALID, "job_manifest root must be a mapping")
    return data


@lru_cache(maxsize=1)
def load_job_manifest() -> dict[str, JobManifestEntry]:
    path = pathmod.job_manifest_path()
    try:
        raw = _load_yaml(path)
    except OSError as exc:
        raise OperatorError(OPERATOR_CONFIG_INVALID, f"Missing job_manifest: {exc}") from exc
    jobs = raw.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise OperatorError(OPERATOR_CONFIG_INVALID, "job_manifest.jobs must be a non-empty list")
    out: dict[str, JobManifestEntry] = {}
    for item in jobs:
        if not isinstance(item, dict):
            raise OperatorError(OPERATOR_CONFIG_INVALID, "job entry must be a mapping")
        job_id = str(item.get("job_id", "")).strip()
        if not job_id:
            raise OperatorError(OPERATOR_CONFIG_INVALID, "job_id required")
        entry = JobManifestEntry(
            job_id=job_id,
            title=str(item.get("title", job_id)),
            note=str(item.get("note", "")),
            intent_keys=tuple(str(x) for x in (item.get("intent_keys") or [])),
            tool_ids=tuple(str(x) for x in (item.get("tool_ids") or [])),
        )
        if not entry.note:
            raise OperatorError(OPERATOR_CONFIG_INVALID, f"note required for job {job_id}")
        out[job_id] = entry
    return out


def clear_manifest_cache() -> None:
    load_job_manifest.cache_clear()


def _jobs_dir_override() -> Path | None:
    """Optional test vault jobs dir via OPERATOR_JOBS_DIR."""
    import os

    raw = os.environ.get("OPERATOR_JOBS_DIR", "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser().resolve()
    return p if p.is_dir() else None


def load_job_primer(job_id: str) -> JobPrimerBundle:
    """Load a Job note. Missing note → JOB_NOT_FOUND."""
    manifest = load_job_manifest()
    entry = manifest.get(job_id)
    if entry is None:
        return JobPrimerBundle(
            ok=False,
            source="job_manifest",
            freshness="unavailable",
            error_code=JOB_NOT_FOUND,
            degraded=True,
            job_id=job_id,
            warnings=[f"Unknown job_id: {job_id}"],
        )

    jobs_dir = _jobs_dir_override() or pathmod.operator_jobs_dir()
    note_path = jobs_dir / entry.note
    settings = get_settings()
    if not note_path.is_file():
        return JobPrimerBundle(
            ok=False,
            source="vault_job",
            freshness="unavailable",
            error_code=JOB_NOT_FOUND,
            degraded=True,
            job_id=job_id,
            title=entry.title,
            primer_path=str(note_path),
            tool_ids=list(entry.tool_ids),
            warnings=[f"Job note missing: {note_path}"],
        )

    text = note_path.read_text(encoding="utf-8")
    truncated = False
    if len(text) > settings.max_job_primer_chars:
        text = text[: settings.max_job_primer_chars] + "\n\n…[truncated by max_job_primer_chars]\n"
        truncated = True

    return JobPrimerBundle(
        ok=True,
        source="vault_job",
        freshness="fresh",
        generated_at=None,
        job_id=job_id,
        title=entry.title,
        primer_markdown=text,
        primer_path=str(note_path.resolve()),
        tool_ids=list(entry.tool_ids),
        max_chars_applied=truncated,
        warnings=["primer truncated"] if truncated else [],
    )
