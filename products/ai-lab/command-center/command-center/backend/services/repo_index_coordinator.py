from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from core.config import settings
from services.channels import channels
from services.index_job_types import ApprovalGate, BuildMetadata, JobPlan, JobType, ValidationResult
from services.index_policy import get_expected_policy_identity, load_index_policy, resolve_index_policy_path
from services.repo_index_state_store import RepoIndexStateStore

# Approval queue is owned by brain and already used by /api/approvals.
from brain.approval_queue.queue import submit as approval_submit  # type: ignore


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RepoIndexState:
    repo_id: str
    dirty: bool = False
    dirty_generation: int = 0
    dirty_since: float | None = None

    debounce_until: float | None = None
    rerun_requested: bool = False

    staging_build_inflight: bool = False
    active_version: str | None = None
    staging_version: str | None = None
    last_build_id: str | None = None

    # Identity of the currently promoted active index (reported by worker).
    # Used to classify drift before scheduling new work.
    active_embedding_model_id_used: str | None = None
    active_embedding_model_revision_used: str | None = None
    active_policy_hash_used: str | None = None
    active_index_schema_version_used: int | None = None
    active_collection_layout_version_used: int | None = None
    last_files_indexed_active: int | None = None

    last_staging_ok_at: float | None = None
    last_promoted_ok_at: float | None = None
    last_error: str | None = None
    incremental_failure_count: int = 0

    pending_approval_id: str | None = None
    blocked_reason: str | None = None
    force_full_rebuild_once: bool = False

    # For large-delta heuristic
    dirty_event_count: int = 0


class RepoIndexCoordinator:
    """
    Hub-side coordinator.

    - Watches repo_watcher signals (mark_dirty).
    - Schedules staging builds (incremental or repo_refresh).
    - Enforces strict validation before promotion.
    - Auto-promotes if validation passes.
    - Submits Gate A/C approvals via approval queue + WS approval event.
    """

    def __init__(self):
        self._states: dict[str, RepoIndexState] = {}
        self._lock = asyncio.Lock()
        self._running = False

        self._store = RepoIndexStateStore(settings.repo_index_state_path)
        self._policy_path = resolve_index_policy_path(settings.index_policy_path)
        self._expected_policy = load_index_policy(self._policy_path)
        self._expected_identity = get_expected_policy_identity(self._expected_policy, self._policy_path)

        # Simple global semaphore for concurrent builds across all repos.
        self._build_sem = asyncio.Semaphore(max(1, int(settings.repo_index_max_concurrent_builds or 1)))

        # Attempt to restore persisted state for continuity (active versions, blocked approvals).
        self._restore_state()

    def _restore_state(self) -> None:
        data = self._store.load()
        if not isinstance(data, dict):
            return
        for repo_id, raw in data.items():
            if not isinstance(raw, dict):
                continue
            st = RepoIndexState(repo_id=repo_id)
            for k, v in raw.items():
                if hasattr(st, k):
                    setattr(st, k, v)
            self._states[repo_id] = st

    def _snapshot_for_persist(self) -> dict[str, Any]:
        return {rid: asdict(st) for rid, st in self._states.items()}

    def _persist_state(self) -> None:
        """
        Snapshot under caller-held lock, flush disk off the event loop when possible.
        Call while holding `_lock` so the snapshot is consistent; IO is not under the lock.
        """
        snap = self._snapshot_for_persist()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._store.save(snap)
            return
        # Fire-and-forget threaded write — do not hold asyncio.Lock across disk IO.
        loop.create_task(asyncio.to_thread(self._store.save, snap))

    async def _persist_state_off_lock(self, snapshot: dict[str, Any] | None = None) -> None:
        """Awaitable flush; prefer for stop() / explicit barriers."""
        if snapshot is None:
            async with self._lock:
                snapshot = self._snapshot_for_persist()
        await asyncio.to_thread(self._store.save, snapshot)

    def get_state_snapshot(self) -> dict[str, Any]:
        return {rid: asdict(st) for rid, st in self._states.items()}

    def _get_state(self, repo_id: str) -> RepoIndexState:
        if repo_id not in self._states:
            self._states[repo_id] = RepoIndexState(repo_id=repo_id)
        return self._states[repo_id]

    def mark_dirty(self, repo_id: str, event_payload: dict[str, Any] | None = None) -> None:
        """
        Called from repo_watcher fast path. Must be fast and non-blocking.
        """
        st = self._get_state(repo_id)
        st.dirty = True
        st.dirty_generation += 1
        st.dirty_event_count += 1
        if st.dirty_since is None:
            st.dirty_since = time.time()
        st.debounce_until = time.time() + (float(settings.repo_index_debounce_ms) / 1000.0)
        if st.staging_build_inflight:
            st.rerun_requested = True
        # Publish dirty marker (non-fatal if nobody listens yet).
        try:
            asyncio.get_running_loop().create_task(
                channels.ops.publish(
                    "repo_index_dirty",
                    {
                        "repo_id": repo_id,
                        "dirty_generation": st.dirty_generation,
                        "timestamp": _now_iso(),
                    },
                )
            )
        except RuntimeError:
            # No loop; ignore (e.g. during shutdown)
            pass

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                # Never crash the coordinator loop.
                await channels.ops.publish(
                    "repo_index_build_failed",
                    {"repo_id": "_system", "error": str(e), "timestamp": _now_iso()},
                )
            await asyncio.sleep(0.5)

    async def stop(self) -> None:
        self._running = False
        # Persist on stop so restart continuity is acceptable (disk off lock).
        async with self._lock:
            snap = self._snapshot_for_persist()
        await self._persist_state_off_lock(snap)

    async def _tick(self) -> None:
        async with self._lock:
            repo_ids = list(self._states.keys())
        for repo_id in repo_ids:
            async with self._lock:
                st = self._states.get(repo_id)
                if not st:
                    continue
                # If blocked on approval, do nothing. The approved tool will perform the rebuild+promote.
                if st.pending_approval_id:
                    continue
                if st.staging_build_inflight:
                    continue
                if not st.dirty:
                    continue
                if st.debounce_until and time.time() < st.debounce_until:
                    continue

                plan = self._classify_job(repo_id, st)
                # Persist state transitions promptly.
                self._persist_state()

            if plan.requires_approval:
                await self._submit_approval(repo_id, plan)
                continue

            await self._start_staging_build(repo_id, plan)

    def _classify_job(self, repo_id: str, st: RepoIndexState) -> JobPlan:
        """
        Implements the user's exact job classification table, using heuristics we can observe in v1:
        - Large delta is inferred from dirty_event_count within the debounce window.
        - Policy mismatch/corruption triggers are v1 TODOs until worker reports identity fields + hub has corruption detectors.
        """
        # Approved escalation should run exactly one forced full rebuild without re-gating.
        if st.force_full_rebuild_once:
            return JobPlan(
                job_type=JobType.full_rebuild_staging_gate_a,
                worker_target="staging",
                worker_mode="full_rebuild",
                force_full=True,
                requires_approval=False,
                approval_gate=None,
            )

        # Gate A: operational confidence thresholds.
        if st.incremental_failure_count >= int(settings.repo_index_incremental_failure_threshold or 0):
            return JobPlan(
                job_type=JobType.full_rebuild_staging_gate_a,
                worker_target="staging",
                worker_mode="full_rebuild",
                force_full=True,
                requires_approval=True,
                approval_gate=ApprovalGate.A,
            )

        changed_docs_ratio = 0.0
        if (st.last_files_indexed_active or 0) > 0:
            changed_docs_ratio = float(st.dirty_event_count) / float(st.last_files_indexed_active or 1)
        if changed_docs_ratio > float(settings.repo_index_changed_docs_ratio_threshold or 1.0):
            return JobPlan(
                job_type=JobType.full_rebuild_staging_gate_a,
                worker_target="staging",
                worker_mode="full_rebuild",
                force_full=True,
                requires_approval=True,
                approval_gate=ApprovalGate.A,
            )

        # Gate C drift detection (policy/schema/embedding drift) based on last promoted active identity.
        # We only gate when we have some identity facts from the active index; otherwise we assume "unknown yet"
        # (e.g. first-time bootstrap).
        has_active_identity = any(
            x is not None
            for x in [
                st.active_policy_hash_used,
                st.active_embedding_model_id_used,
                st.active_embedding_model_revision_used,
                st.active_index_schema_version_used,
                st.active_collection_layout_version_used,
            ]
        )
        if has_active_identity:
            drift_reasons: list[str] = []
            if st.active_policy_hash_used is not None and st.active_policy_hash_used != self._expected_identity.policy_hash:
                drift_reasons.append("policy_hash_mismatch")
            if st.active_embedding_model_id_used is not None and st.active_embedding_model_id_used != self._expected_identity.embedding_model_id:
                drift_reasons.append("embedding_model_id_mismatch")
            if st.active_embedding_model_revision_used is not None and st.active_embedding_model_revision_used != self._expected_identity.embedding_model_revision:
                drift_reasons.append("embedding_model_revision_mismatch")
            if st.active_index_schema_version_used is not None and st.active_index_schema_version_used != self._expected_identity.index_schema_version:
                drift_reasons.append("index_schema_version_mismatch")
            if st.active_collection_layout_version_used is not None and st.active_collection_layout_version_used != self._expected_identity.collection_layout_version:
                drift_reasons.append("collection_layout_version_mismatch")

            if drift_reasons:
                return JobPlan(
                    job_type=JobType.full_rebuild_staging_gate_c,
                    worker_target="staging",
                    worker_mode="full_rebuild",
                    force_full=True,
                    requires_approval=True,
                    approval_gate=ApprovalGate.C,
                )

        # Large delta / catch-up: treat as repo_refresh (still staging, no approval).
        if st.dirty_event_count >= int(settings.repo_index_large_delta_events_threshold or 0):
            return JobPlan(
                job_type=JobType.repo_refresh_staging,
                worker_target="staging",
                worker_mode="repo_refresh",
                force_full=False,
                requires_approval=False,
                approval_gate=None,
            )

        # Default: incremental staging update.
        return JobPlan(
            job_type=JobType.incremental_staging,
            worker_target="staging",
            worker_mode="incremental",
            force_full=False,
            requires_approval=False,
            approval_gate=None,
        )

    async def _start_staging_build(self, repo_id: str, plan: JobPlan) -> None:
        async with self._build_sem:
            async with self._lock:
                st = self._get_state(repo_id)
                st.staging_build_inflight = True
                if plan.force_full:
                    st.force_full_rebuild_once = False
                # Reset event count for next generation window.
                st.dirty_event_count = 0
                self._persist_state()

            await channels.ops.publish(
                "repo_index_build_started",
                {"repo_id": repo_id, "job_type": plan.job_type.value, "timestamp": _now_iso()},
            )

            try:
                # Worker API contract v1: we forward to worker op "index_repo".
                # The worker must support target=staging + return identity metadata in result.meta.
                build_raw = await self._worker_index_repo(
                    {
                        "repo_id": repo_id,
                        "target": "staging",
                        "mode": plan.worker_mode,
                        "force_full": plan.force_full,
                        # Also send expected identity for logging/worker-side checks (worker must not treat as authority).
                        "expected_policy_hash": self._expected_identity.policy_hash,
                        "expected_embedding_model_id": self._expected_identity.embedding_model_id,
                        "expected_index_schema_version": self._expected_identity.index_schema_version,
                    }
                )

                meta = self._parse_build_metadata(repo_id, build_raw)
                validation = await self._validate_staging_build(repo_id, meta)
                if validation.ok:
                    await self._promote(repo_id, meta)
                else:
                    await self._handle_validation_failure(repo_id, meta, validation)
            except Exception as e:
                await self._handle_build_failure(repo_id, str(e))
            finally:
                async with self._lock:
                    st = self._get_state(repo_id)
                    st.staging_build_inflight = False
                    self._persist_state()

    def _parse_build_metadata(self, repo_id: str, build_raw: dict[str, Any]) -> BuildMetadata:
        """
        Normalize worker response into BuildMetadata.
        Supports both:
        - worker returning fields at top-level, and/or
        - worker returning them under result/meta.
        """
        data = build_raw or {}
        result = data.get("result") if isinstance(data.get("result"), dict) else data
        meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}

        def _get(key: str, default=None):
            if key in result:
                return result.get(key)
            if key in meta:
                return meta.get(key)
            return default

        errors = _get("errors", []) or []
        warnings = _get("warnings", []) or []
        if not isinstance(errors, list):
            errors = [str(errors)]
        if not isinstance(warnings, list):
            warnings = [str(warnings)]

        def _maybe_int(v):
            try:
                return int(v) if v is not None else None
            except Exception:
                return None

        return BuildMetadata(
            repo_id=str(_get("repo_id", repo_id)),
            target=str(_get("target", _get("index_target", "staging"))),
            build_id=str(_get("build_id", _get("id", "")) or ""),
            staging_version=_get("staging_version"),
            active_version_seen=_get("active_version_seen"),
            embedding_model_id_used=_get("embedding_model_id_used"),
            embedding_model_revision_used=_get("embedding_model_revision_used"),
            policy_hash_used=_get("policy_hash_used"),
            index_schema_version_used=_maybe_int(_get("index_schema_version_used")),
            collection_layout_version_used=_maybe_int(_get("collection_layout_version_used")),
            metadata_readable=_get("metadata_readable"),
            corruption_detected=_get("corruption_detected"),
            files_considered=_maybe_int(_get("files_considered")),
            files_indexed=_maybe_int(_get("files_indexed")),
            chunks_indexed=_maybe_int(_get("chunks_indexed")),
            started_at=_get("started_at"),
            finished_at=_get("finished_at"),
            warnings=[str(w) for w in warnings],
            errors=[str(e) for e in errors],
            raw=result if isinstance(result, dict) else {"raw": result},
        )

    async def _validate_staging_build(self, repo_id: str, meta: BuildMetadata) -> ValidationResult:
        reasons: list[str] = []

        # Required worker-reported metadata for strict hub governance.
        required_fields_missing: list[str] = []
        if not (meta.embedding_model_id_used or "").strip():
            required_fields_missing.append("embedding_model_id_used")
        if not (meta.embedding_model_revision_used or "").strip():
            required_fields_missing.append("embedding_model_revision_used")
        if not (meta.policy_hash_used or "").strip():
            required_fields_missing.append("policy_hash_used")
        if meta.index_schema_version_used is None:
            required_fields_missing.append("index_schema_version_used")
        if meta.collection_layout_version_used is None:
            required_fields_missing.append("collection_layout_version_used")
        if meta.metadata_readable is None:
            required_fields_missing.append("metadata_readable")
        if meta.corruption_detected is None:
            required_fields_missing.append("corruption_detected")
        if required_fields_missing:
            reasons.extend([f"missing_required_metadata:{f}" for f in required_fields_missing])
            return ValidationResult(ok=False, severity="gate_a", reasons=reasons)

        # Identity checks (strict)
        if (meta.embedding_model_id_used or "") != (self._expected_identity.embedding_model_id or ""):
            reasons.append("embedding_model_id_mismatch")
        if (meta.embedding_model_revision_used or "") != (self._expected_identity.embedding_model_revision or ""):
            reasons.append("embedding_model_revision_mismatch")
        if (meta.policy_hash_used or "") != (self._expected_identity.policy_hash or ""):
            reasons.append("policy_hash_mismatch")
        if meta.index_schema_version_used is None or meta.index_schema_version_used != self._expected_identity.index_schema_version:
            reasons.append("index_schema_version_mismatch")
        if meta.collection_layout_version_used is None or meta.collection_layout_version_used != self._expected_identity.collection_layout_version:
            reasons.append("collection_layout_version_mismatch")
        if (meta.target or "") != "staging":
            reasons.append("target_not_staging")

        # Build sanity
        if not meta.build_id:
            reasons.append("missing_build_id")
        if not meta.staging_version:
            reasons.append("missing_staging_version")
        if meta.errors:
            reasons.append("worker_reported_errors")
        if meta.metadata_readable is False:
            reasons.append("index_metadata_unreadable")
        if meta.corruption_detected is True:
            reasons.append("index_corruption_detected")

        # If we have identity mismatch, this is Gate C.
        if any(
            r in reasons
            for r in [
                "policy_hash_mismatch",
                "embedding_model_id_mismatch",
                "embedding_model_revision_mismatch",
                "index_schema_version_mismatch",
                "collection_layout_version_mismatch",
            ]
        ):
            return ValidationResult(ok=False, severity="gate_c", reasons=reasons)

        # Retrieval smoke test: must hit staging before promote (worker contract: target=staging).
        try:
            smoke_query = (settings.repo_index_smoke_test_query or "smoke").strip()[:300]
            out = await self._worker_retrieve({"query": smoke_query, "target": "staging"})
            if not isinstance(out, dict) or out.get("ok") is not True:
                reasons.append("smoke_test_bridge_failed")
            else:
                wr = out.get("result")
                if not isinstance(wr, dict):
                    reasons.append("smoke_test_empty_response")
                elif wr.get("ok") is False:
                    reasons.append("smoke_test_worker_not_ok")
        except Exception:
            # Likely transient tunnel failure; retryable.
            reasons.append("smoke_test_failed")
            return ValidationResult(ok=False, severity="retryable", reasons=reasons)

        if reasons:
            # Any non-identity validation failure is treated as integrity risk (Gate A policy).
            return ValidationResult(ok=False, severity="gate_a", reasons=reasons)
        return ValidationResult(ok=True, severity="ok", reasons=[])

    async def _promote(self, repo_id: str, meta: BuildMetadata) -> None:
        if not meta.staging_version:
            await self._handle_validation_failure(
                repo_id, meta, ValidationResult(ok=False, severity="escalate", reasons=["missing_staging_version"])
            )
            return

        # Promote should be automatic (no Gate B) when validation is clean.
        res = await self._worker_promote_repo_index({"repo_id": repo_id, "staging_version": meta.staging_version})

        async with self._lock:
            st = self._get_state(repo_id)
            st.active_version = meta.staging_version
            st.staging_version = meta.staging_version
            st.last_build_id = meta.build_id
            st.last_promoted_ok_at = time.time()
            st.last_staging_ok_at = time.time()

            # Persist identity for next drift classification.
            st.active_embedding_model_id_used = meta.embedding_model_id_used
            st.active_embedding_model_revision_used = meta.embedding_model_revision_used
            st.active_policy_hash_used = meta.policy_hash_used
            st.active_index_schema_version_used = meta.index_schema_version_used
            st.active_collection_layout_version_used = meta.collection_layout_version_used
            st.last_files_indexed_active = meta.files_indexed

            # If changes happened during build, keep dirty and schedule another debounce.
            if st.rerun_requested:
                st.dirty = True
                st.rerun_requested = False
                st.debounce_until = time.time() + (float(settings.repo_index_debounce_ms) / 1000.0)
            else:
                st.dirty = False
                st.dirty_since = None
                st.debounce_until = None

            st.last_error = None
            st.incremental_failure_count = 0
            st.force_full_rebuild_once = False
            self._persist_state()

        await channels.ops.publish(
            "repo_index_promoted",
            {"repo_id": repo_id, "active_version": meta.staging_version, "timestamp": _now_iso(), "result": res},
        )

    async def _handle_validation_failure(self, repo_id: str, meta: BuildMetadata, validation: ValidationResult) -> None:
        async with self._lock:
            st = self._get_state(repo_id)
            st.last_error = ",".join(validation.reasons[:3]) if validation.reasons else "validation_failed"
            st.incremental_failure_count += 1
            self._persist_state()

        await channels.ops.publish(
            "repo_index_build_failed",
            {
                "repo_id": repo_id,
                "error": "validation_failed",
                "severity": validation.severity,
                "reasons": validation.reasons,
                "timestamp": _now_iso(),
            },
        )

        # Retry policy: max N retries; exponential backoff; collapse newer dirty events into next rerun.
        if validation.severity == "retryable":
            # Simple v1 behavior: just mark dirty again and backoff; coordinator will attempt later.
            backoff_s = 1.5
            await asyncio.sleep(backoff_s)
            async with self._lock:
                st = self._get_state(repo_id)
                st.dirty = True
                st.debounce_until = time.time() + backoff_s
                self._persist_state()
            return

        # Escalate path: Gate C or Gate A (corruption detectors to be added).
        if validation.severity == "gate_a":
            await self._submit_repo_index_approval(
                repo_id=repo_id,
                gate=ApprovalGate.A,
                reason="integrity_or_validation_failure",
                detail=f"Gate A: full rebuild required for repo {repo_id} due to integrity/validation failure.",
                extra={
                    "validation_reasons": validation.reasons,
                    "current_active_version": meta.active_version_seen,
                    "reported_metadata_readable": meta.metadata_readable,
                    "reported_corruption_detected": meta.corruption_detected,
                    "required_worker_metadata_contract": [
                        "embedding_model_id_used",
                        "embedding_model_revision_used",
                        "policy_hash_used",
                        "index_schema_version_used",
                        "collection_layout_version_used",
                        "metadata_readable",
                        "corruption_detected",
                    ],
                },
            )
            return

        if validation.severity == "gate_c":
            await self._submit_repo_index_approval(
                repo_id=repo_id,
                gate=ApprovalGate.C,
                reason="policy_or_schema_mismatch",
                detail=f"Gate C: policy/schema mismatch for repo {repo_id}. Do full rebuild staging then promote.",
                extra={
                    "repo_id": repo_id,
                    "gate": "C",
                    "reason": "policy_or_schema_mismatch",
                    "expected_policy_hash": self._expected_identity.policy_hash,
                    "reported_policy_hash": meta.policy_hash_used,
                    "expected_embedding_model_id": self._expected_identity.embedding_model_id,
                    "reported_embedding_model_id": meta.embedding_model_id_used,
                    "expected_index_schema_version": self._expected_identity.index_schema_version,
                    "reported_index_schema_version": meta.index_schema_version_used,
                    "current_active_version": meta.active_version_seen,
                },
            )
            return

        # Unknown escalation; keep active pinned.
        async with self._lock:
            st = self._get_state(repo_id)
            st.blocked_reason = "validation_degraded_or_conflicting"
            self._persist_state()

    async def _handle_build_failure(self, repo_id: str, error: str) -> None:
        async with self._lock:
            st = self._get_state(repo_id)
            st.last_error = (error or "build_failed")[:200]
            st.incremental_failure_count += 1
            # Keep dirty so it can retry.
            st.dirty = True
            st.debounce_until = time.time() + 2.0
            self._persist_state()
        await channels.ops.publish("repo_index_build_failed", {"repo_id": repo_id, "error": str(error), "timestamp": _now_iso()})

    async def _submit_approval(self, repo_id: str, plan: JobPlan) -> None:
        # Currently only used if we add pre-classified A/C plans; v1 classification uses validation mismatch.
        gate = plan.approval_gate or ApprovalGate.C
        await self._submit_repo_index_approval(
            repo_id=repo_id,
            gate=gate,
            reason="classified_full_rebuild",
            detail=f"Gate {gate.value}: full rebuild required for repo {repo_id}.",
            extra={
                "repo_id": repo_id,
                "gate": gate.value,
                "reason": "classified_full_rebuild",
                "expected_policy_hash": self._expected_identity.policy_hash,
                "expected_embedding_model_id": self._expected_identity.embedding_model_id,
                "expected_index_schema_version": self._expected_identity.index_schema_version,
                "reported_policy_hash": self._get_state(repo_id).active_policy_hash_used,
                "reported_embedding_model_id": self._get_state(repo_id).active_embedding_model_id_used,
                "reported_index_schema_version": self._get_state(repo_id).active_index_schema_version_used,
                "current_active_version": self._get_state(repo_id).active_version,
            },
        )

    async def _submit_repo_index_approval(
        self,
        repo_id: str,
        gate: ApprovalGate,
        reason: str,
        detail: str,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit a structured request to the approval queue AND publish a WS approval event so UI updates immediately.
        Uses existing approval execution path: /api/approvals/resolve -> brain/execution.run(tool_name, args).
        """
        spec = {
            "agent": "repo_index_coordinator",
            "action": "repo_index_rebuild" if gate == ApprovalGate.A else "repo_index_policy_migration",
            "reason": detail,
            "detail": detail,
            "gate": gate.value,
            "repo_id": repo_id,
            "status": "pending",
            "created_at": _now_iso(),
        }
        if extra:
            spec.update(extra)
        apr_id = await asyncio.to_thread(approval_submit, spec)
        async with self._lock:
            st = self._get_state(repo_id)
            st.pending_approval_id = apr_id
            st.blocked_reason = f"pending_gate_{gate.value}"
            self._persist_state()

        await channels.control.publish(
            "approval",
            {
                "id": apr_id,
                "type": "approval",
                "agent": spec["agent"],
                "action": spec["action"],
                "detail": spec["detail"],
                "status": "pending",
                "timestamp": spec["created_at"],
                "gate": gate.value,
            },
        )
        return apr_id

    async def handle_approval_resolution(self, approval_id: str, resolution: str, spec: dict[str, Any] | None = None) -> None:
        """
        Resume coordinator flow after approval resolution for Gate A/C.
        Uses queue-resolved spec payload from /api/approvals/resolve.
        """
        spec = spec or {}
        repo_id = str(spec.get("repo_id") or "").strip()
        if not repo_id:
            return
        async with self._lock:
            st = self._get_state(repo_id)
            if st.pending_approval_id != approval_id:
                return
            st.pending_approval_id = None
            if resolution == "approved":
                st.force_full_rebuild_once = True
                st.blocked_reason = None
                st.dirty = True
                st.debounce_until = time.time()
            else:
                st.blocked_reason = "approval_denied"
            self._persist_state()

    # Worker calls (via tunnel)
    async def _worker_index_repo(self, payload: dict[str, Any]) -> dict[str, Any]:
        from services.supervisor_bridge import route_intent
        # Use supervisor bridge so reads are audited and go through one path.
        return await route_intent(agent="repo_index_coordinator", op="index_repo", payload=payload)

    async def _worker_retrieve(self, payload: dict[str, Any]) -> dict[str, Any]:
        from services.supervisor_bridge import route_intent
        return await route_intent(agent="repo_index_coordinator", op="retrieve", payload=payload)

    async def _worker_promote_repo_index(self, payload: dict[str, Any]) -> dict[str, Any]:
        from services.supervisor_bridge import route_intent
        return await route_intent(agent="repo_index_coordinator", op="promote_repo_index", payload=payload)


# Singleton, wired in main.py and used by repo_watcher fast path.
coordinator: RepoIndexCoordinator | None = None


def get_coordinator() -> RepoIndexCoordinator:
    global coordinator
    if coordinator is None:
        coordinator = RepoIndexCoordinator()
    return coordinator

