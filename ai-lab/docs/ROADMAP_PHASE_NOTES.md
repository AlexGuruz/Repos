# Roadmap phase notes (human approvals)

## Phase 1 — Approval Enforcement Parity

**Status:** Accepted (human review).

**Saved approval (paraphrased):** Phase 1 accepted. Proceed to Phase 2 after recording the watch item below.

**Watch item — governance (do not regress):**

- Metadata quality in `brain/tool_registry.py` remains a **governance dependency**.
- **Do not** add new write-capable or state-changing tools without complete approval metadata (`approval_required`, `side_effects`, and related fields). Fail-closed execution depends on this.

**Doc reference:** `docs/APPROVAL_ENFORCEMENT_PARITY.md`

## Phase 2 — Personal Ops Snapshot Upgrade

**Status:** Implemented; pending human sign-off before Phase 3.

**Goal (scoped):** Make `personal_ops_snapshot` useful for **daily planning** (not a full personal assistant everywhere).

**Deliverables:** `docs/PERSONAL_OPS_SNAPSHOT_PLAN.md`, enriched `build_personal_ops_snapshot`, loader selection tweak, `tests/test_personal_ops_snapshot.py`.
