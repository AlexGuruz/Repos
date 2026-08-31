"""POST /index_repo — legacy direct upsert, or staging-only build (command-center contract)."""

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from worker_assistant.app.models.schemas import IndexRepoBody, SuccessResponse
from worker_assistant.app.services import chroma_store
from worker_assistant.app.services.chunker import chunk_text, read_text_file
from worker_assistant.app.services.embedder import embed_texts
from worker_assistant.app.services.file_walker import iter_indexable_files
from worker_assistant.app.services.index_policy_loader import load_index_policy_identity
from worker_assistant.app.services.index_state_report import utc_now_iso
from worker_assistant.app.services.indexing_policy import IndexingPolicy
from worker_assistant.app.services.repo_index_pointers import (
    PointerEntry,
    RepoPointerFile,
    load_pointer_file,
    save_pointer_file_atomic,
    snapshot_collection_name,
    write_manifest,
)
from worker_assistant.app.services.repo_registry import RepoSpec, get_repo_spec, load_registry

router = APIRouter()


def _stable_id(repo_id: str, file_path: str, start: int, end: int) -> str:
    h = hashlib.sha256(f"{repo_id}:{file_path}:{start}:{end}".encode("utf-8")).hexdigest()
    return h


def _resolve_repo(body: IndexRepoBody) -> tuple[str, RepoSpec]:
    registry_path = Path("worker_assistant") / "config" / "repos.yaml"
    repo_id = (body.repo_id or "").strip()
    repo_path_raw = (body.repo_path or "").strip()
    if repo_id:
        try:
            registry = load_registry(registry_path)
            spec = get_repo_spec(registry, repo_id)
            return repo_id, spec
        except KeyError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if repo_path_raw:
        repo_path = Path(repo_path_raw).resolve()
        rid = repo_path.name.lower().replace(" ", "-")
        return rid, RepoSpec(repo_id=rid, path=repo_path, include=["."], exclude=[])
    raise HTTPException(status_code=400, detail="repo_id or repo_path is required")


def _staging_version_tag() -> str:
    return datetime.now(timezone.utc).strftime("gen_%Y%m%d_%H%M%S")


@router.post("/index_repo", response_model=SuccessResponse)
async def index_repo(body: IndexRepoBody, request: Request):
    task = "index_repo"
    if getattr(request.app.state, "read_only", True):
        raise HTTPException(
            status_code=503,
            detail="Governance read-only: set AI_LAB_* env and run verify_governance before starting.",
        )

    repo_id, spec = _resolve_repo(body)
    repo_path = spec.path.resolve()
    if not repo_path.exists():
        raise HTTPException(status_code=400, detail=f"Repo path does not exist: {repo_path}")

    target = body.target
    if target is None:
        return _legacy_index_repo(repo_id, spec, repo_path, task)

    if target != "staging":
        raise HTTPException(status_code=400, detail='target must be "staging" for hub builds')

    identity = load_index_policy_identity()
    policy = IndexingPolicy()
    files = iter_indexable_files(spec, policy)
    warnings: list[str] = []
    errors: list[str] = []

    if body.expected_policy_hash and body.expected_policy_hash != identity.policy_hash:
        warnings.append(
            "expected_policy_hash does not match worker index_policy.yaml (reporting worker actuals)"
        )
    if body.expected_embedding_model_id and body.expected_embedding_model_id != identity.embedding_model_id:
        warnings.append("expected_embedding_model_id does not match worker policy file")
    if body.expected_index_schema_version is not None and int(
        body.expected_index_schema_version
    ) != int(identity.index_schema_version):
        warnings.append("expected_index_schema_version does not match worker policy file")

    started_at = utc_now_iso()
    ptr_before = load_pointer_file(repo_id)
    active_version_seen = ptr_before.active.version if ptr_before.active else None

    build_id = f"build_{uuid.uuid4().hex[:12]}"
    staging_version = _staging_version_tag()
    collection_name = snapshot_collection_name(repo_id, staging_version)
    model_hf = identity.sentence_transformers_model

    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    files_with_chunks: set[str] = set()

    for f in files:
        try:
            text = read_text_file(f)
        except Exception:
            continue
        rel = str(f.resolve())
        for ch in chunk_text(text):
            ids.append(_stable_id(repo_id, rel, ch.start, ch.end))
            docs.append(ch.text)
            files_with_chunks.add(rel)
            metas.append(
                {
                    "repo_id": repo_id,
                    "path": rel,
                    "start": ch.start,
                    "end": ch.end,
                }
            )

    files_considered = len(files)
    files_indexed = len(files_with_chunks)
    chunks_indexed = len(docs)

    base_meta = {
        "repo_id": repo_id,
        "target": "staging",
        "build_id": build_id,
        "staging_version": staging_version,
        "active_version_seen": active_version_seen,
        "embedding_model_id_used": identity.embedding_model_id,
        "embedding_model_revision_used": identity.embedding_model_revision,
        "policy_hash_used": identity.policy_hash,
        "index_schema_version_used": identity.index_schema_version,
        "collection_layout_version_used": identity.collection_layout_version,
        "files_considered": files_considered,
        "files_indexed": files_indexed,
        "chunks_indexed": chunks_indexed,
        "started_at": started_at,
        "mode": body.mode,
        "force_full": body.force_full,
    }

    if not docs:
        finished_at = utc_now_iso()
        errors.append("No indexable documents found (check include/exclude and file extensions).")
        meta = {
            **base_meta,
            "finished_at": finished_at,
            "metadata_readable": False,
            "corruption_detected": False,
        }
        return SuccessResponse(
            task=task,
            repo_id=repo_id,
            summary="Staging build produced no chunks.",
            warnings=warnings + ["Nothing indexed (check include/exclude and file extensions)."],
            errors=errors,
            meta=meta,
        )

    if ptr_before.staging:
        chroma_store.delete_collection_by_name(ptr_before.staging.collection_name)

    embeddings = embed_texts(docs, model_name=model_hf)
    col_meta = {
        "repo_id": repo_id,
        "snapshot_version": staging_version,
        "index_kind": "staging",
    }
    chroma_store.upsert_chunks_named(
        collection_name=collection_name,
        ids=ids,
        documents=docs,
        embeddings=embeddings,
        metadatas=metas,
        collection_metadata=col_meta,
    )

    count_after = chroma_store.collection_count(collection_name)
    corruption_detected = count_after != len(ids)
    finished_at = utc_now_iso()

    manifest = {
        **base_meta,
        "finished_at": finished_at,
        "collection_name": collection_name,
        "metadata_readable": True,
        "corruption_detected": corruption_detected,
        "embedding_model_id_used": identity.embedding_model_id,
        "embedding_model_revision_used": identity.embedding_model_revision,
        "policy_hash_used": identity.policy_hash,
        "index_schema_version_used": identity.index_schema_version,
        "collection_layout_version_used": identity.collection_layout_version,
    }
    try:
        write_manifest(repo_id, staging_version, manifest)
    except Exception:
        manifest["metadata_readable"] = False

    new_state = RepoPointerFile(
        active=ptr_before.active,
        staging=PointerEntry(version=staging_version, collection_name=collection_name),
        previous_active=ptr_before.previous_active,
    )
    save_pointer_file_atomic(repo_id, new_state)

    if corruption_detected:
        errors.append(f"Integrity check: expected {len(ids)} vectors, found {count_after}")

    summary_msg = f"Staging index {staging_version}: {chunks_indexed} chunks from {files_indexed} files."
    try:
        import governance_bridge as gb

        gb.log_action_after("worker_7b", "index_repo", repo_id, summary_msg)
    except Exception:
        pass

    return SuccessResponse(
        task=task,
        repo_id=repo_id,
        summary=summary_msg,
        warnings=warnings,
        errors=errors,
        meta={
            **base_meta,
            "finished_at": finished_at,
            "metadata_readable": bool(manifest.get("metadata_readable", True)),
            "corruption_detected": corruption_detected,
        },
    )


def _legacy_index_repo(
    repo_id: str,
    spec: RepoSpec,
    repo_path: Path,
    task: str,
) -> SuccessResponse:
    """Pre-contract behavior: upsert into single repo_* collection (active use)."""
    policy = IndexingPolicy()
    files = iter_indexable_files(spec, policy)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    for f in files:
        try:
            text = read_text_file(f)
        except Exception:
            continue
        rel = str(f.resolve())
        for ch in chunk_text(text):
            ids.append(_stable_id(repo_id, rel, ch.start, ch.end))
            docs.append(ch.text)
            metas.append(
                {
                    "repo_id": repo_id,
                    "path": rel,
                    "start": ch.start,
                    "end": ch.end,
                }
            )
    if not docs:
        return SuccessResponse(
            task=task,
            repo_id=repo_id,
            summary="No indexable documents found.",
            warnings=["Nothing indexed (check include/exclude and file extensions)."],
            meta={"files_considered": len(files)},
        )
    identity = load_index_policy_identity()
    embeddings = embed_texts(docs, model_name=identity.sentence_transformers_model)
    chroma_store.upsert_chunks(repo_id=repo_id, ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
    summary_msg = f"Indexed {len(docs)} chunks from {len(files)} files."
    try:
        import governance_bridge as gb

        gb.log_action_after("worker_7b", "index_repo", repo_id, summary_msg)
    except Exception:
        pass
    return SuccessResponse(
        task=task,
        repo_id=repo_id,
        summary=summary_msg,
        meta={
            "repo_path": str(repo_path),
            "files_indexed": len(files),
            "chunks_indexed": len(docs),
            "chroma_path": str(chroma_store.get_chroma_path()),
            "embedding_model_id_used": identity.embedding_model_id,
            "policy_hash_used": identity.policy_hash,
        },
    )
