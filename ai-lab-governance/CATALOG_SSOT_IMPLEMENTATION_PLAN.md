# System catalog (machine-checkable inventory) — implementation plan

**Repo:** `ai-lab-governance`  
**Version:** 0.1 (planning)  
**Audience:** Engineering agent / implementer  
**Status:** Specification only — no code in this phase

---

## 1. Purpose

### 1.1 What this catalog is for

This catalog is the **canonical inventory and operational truth layer** for the local AI lab: which **components** exist, how mature each **capability** is, which **source wins** when docs/code/infra conflict, which **environment** runs what, and **who** owns code, deployment, runtime, and approvals.

It is consumed by:

- Humans (review, onboarding, incident response)
- CI (schema validation, optional drift checks)
- Future orchestrator/agent surfaces (read-only “what exists / what is authoritative”)

### 1.2 Problem solved

Today, cross-repo truth lives in prose (`plan.md`, READMEs) and mental models. That drifts. Agents and humans infer “built,” “partial,” and “owner” inconsistently. **Governance** already answers *what automation may do*; it does **not** answer *what systems exist* or *what is actually verified as built*.

### 1.3 Why governance alone is not enough


| Layer                     | Answers                                                                                                   |
| ------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Governance** (existing) | Approval tiers, allowlists, denied actions, tool registry contracts, repo **risk** classes                |
| **Catalog** (this work)   | Component inventory, capability maturity, authority/precedence, multi-axis ownership, environment mapping |
| **Verification**          | Observed evidence (artifacts, deploys, health, repo shape) attached to catalog entries                    |


Mixing inventory into `GLOBAL_POLICY.md` or `repo_classes.yaml` would **conflate risk posture with product maturity** and make both drift faster. **Repo class** = how automation is allowed to touch a path/repo. **Capability maturity** = how complete the product/system is. They must stay separate.

---

## 2. What must not be broken

### 2.1 Existing files and workflows

- [GLOBAL_POLICY.md](e:/Repos/ai-lab-governance/GLOBAL_POLICY.md), [policies/*.yaml](e:/Repos/ai-lab-governance/policies/), [wrappers/*.py](e:/Repos/ai-lab-governance/wrappers/), [registry/tool_registry.json](e:/Repos/ai-lab-governance/registry/tool_registry.json), and [bootstrap/verify_governance.py](e:/Repos/ai-lab-governance/bootstrap/verify_governance.py) must **continue to function** for current consumers.
- Adding catalog artifacts must be **additive**: new schemas, new registry YAML, new scripts, and **minimal** extensions to `verify_governance.py` (e.g. optional or gated checks) — not rewrites of approval logic.

### 2.2 Approval logic

- No change that **weakens** T0–T4 semantics or bypasses wrappers for state-changing actions.
- Catalog edits are **data**; changing them is a state change and must remain subject to the same governance rules as other repo edits (human PR review; agents do not silently mutate — Section 10).

### 2.3 Repo classification vs product maturity

- [policies/repo_classes.yaml](e:/Repos/ai-lab-governance/policies/repo_classes.yaml) remains the SSoT for **automation risk class** (`docs_internal`, `tooling_internal`, etc.).
- Catalog **must not** duplicate repo class as “maturity.” Linkage is allowed: e.g. `repo_registry.json` entries may reference `repo_class` **by id** for convenience, but **capability maturity** lives only on **components** in `registry/components.yaml`.

### 2.4 Agent write restrictions

- Hard rule from [AGENTS.md](e:/Repos/ai-lab-governance/AGENTS.md) remains: no unwrapped state-changing automation. Catalog files are **high-impact**; treat edits like policy-adjacent data (PR-only, no silent agent writes).

---

## 3. Definitions


| Term                    | Definition                                                                                                                                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Governance**          | Rules for **what actors may do**: tiers, allowlists, denials, tool registry **contracts**, execution paths (wrappers), logging.                                                                            |
| **Catalog**             | **Declared** model: components, environments, authority bindings, ownership axes, intended lifecycle roll-ups, capability matrix, **references** to evidence slots (not proof by itself).                  |
| **Verification**        | Process and artifacts that attach **observed** facts to catalog entries (CI jobs, manual attestations with timestamp, external probes).                                                                    |
| **Evidence**            | A structured record that a check ran and what it saw (pass/fail, URI, commit SHA, timestamp). Supports **trust, not opinion**, for “built.”                                                                |
| **Authority**           | For a **domain** (e.g. API shape), which **source kind** and **canonical ref** is normative, plus **precedence** when multiple sources exist.                                                              |
| **Ownership**           | **code_owner**, **deploy_owner**, **runtime_owner**, **approval_owner** (recommended): distinct responsibilities; never a single vague `owner`.                                                            |
| **Lifecycle state**     | Top-level roll-up enum (planned / partial / built / deprecated). **Not sufficient alone** for “partial” or “built” semantics — capabilities + evidence rule.                                               |
| **Capability maturity** | Per-capability enum (e.g. unbuilt / partial / built / na) — **authoritative** for “how done” a slice is; roll-up is derived or declarative but must not contradict capability facts without justification. |
| **Drift**               | Mismatch between **declared** catalog (including claimed lifecycle/evidence expectations) and **observed** verification results or mandatory repo shape.                                                   |


**Triad (must stay explicit):**

- Catalog = declared model (systems, authority, ownership, intended lifecycle).
- Verification = observed reality **attached** to that model.
- Governance = what actors may do **to catalog and to verification** (and everything else in scope).

---

## 4. Design principles

1. **Catalog declares intended truth** — YAML/JSON under `registry/`, validated by JSON Schema.
2. **Verification attaches observed evidence** — `evidence{}` + `last_verified_at`; “built” requires **satisfying evidence rules** (Section 7).
3. **Governance controls what may change** — Editing catalog or running drift probes follows policy; governance does **not** replace catalog content.
4. **No silent edits** — Catalog changes via tracked VCS, PR review; signed/attested **external** evidence files are **v2+** (Section 5.6); v1 uses inline evidence only.
5. **No vague maturity labels** — “Partial” = capability matrix; top-level `lifecycle_state` is secondary summary.
6. **Machine-checkable over prose** — Prose docs may be **generated** from catalog later; hand-maintained tables in README are non-canonical.

**Hard invariant — `lifecycle_state: built` (normative):** A component **must not** claim `lifecycle_state: built` unless **all** evidence entries with `required_for_lifecycle: true` have `status: pass` **and** each such entry’s `observed_at` falls within the **allowed freshness window** (max age defined by policy env var or catalog config — see Section 7). Validators and CI **must** enforce this invariant in strict mode so agent implementations and human edits cannot reinterpret “built” loosely. This restates and tightens principle 2 for the `built` case only; capability roll-up and `lifecycle_override_reason` guardrails (Section 5.3) still apply.

---

## 5. Canonical data model

### 5.1 Component (logical shape)

**Storage:** `registry/components.yaml` — document array or keyed map (implementer chooses one consistent style; schema must enforce uniqueness of `id`).


| Field                       | Required    | Type / notes                                                                                                                                  |
| --------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                        | yes         | Stable slug, `kebab-case`                                                                                                                     |
| `display_name`              | yes         | Human string                                                                                                                                  |
| `primary_repo`              | yes         | Logical repo id (see `repo_registry.json`)                                                                                                    |
| `related_repos`             | no          | string[] of repo ids                                                                                                                          |
| `component_type`            | yes         | enum: `application`, `library`, `platform`, `infra`, `documentation`, `worker_runtime`, `config_secrets_plane`, … (extensible enum in schema) |
| `lifecycle_state`           | yes         | `planned` | `partial` | `built` | `deprecated`                                                                                              |
| `capabilities`              | yes         | Map capability_key → maturity (Section 5.3)                                                                                                   |
| `authority`                 | yes         | Map domain → authority binding (Section 5.4)                                                                                                  |
| `code_owner`                | yes         | string (team or role id, e.g. `lab-core`)                                                                                                     |
| `deploy_owner`              | yes         | string                                                                                                                                        |
| `runtime_owner`             | yes         | string (often references environment id or machine class)                                                                                     |
| `approval_owner`            | recommended | string — who must approve high-risk changes                                                                                                   |
| `environments`              | yes         | Map `environment_id` → deployment binding (Section 5.5)                                                                                       |
| `evidence`                  | yes         | Map evidence_key → evidence spec; v1 results **inline** (`status`, `observed_at`, optional embedded `last_result`) — Section 5.6              |
| `last_verified_at`          | yes         | ISO-8601 UTC or `null` if never verified                                                                                                      |
| `lifecycle_override_reason` | no          | Required when roll-up rule is violated; triggers **mandatory CI warning** + `approval_owner` review — Section 5.3                             |


**Rule — built vs declaration:**

- **Invariant (same as Section 4):** A component must not claim `lifecycle_state: built` unless every evidence entry with `required_for_lifecycle: true` has `status: pass` and `observed_at` within the allowed freshness window.
- Schema **cannot** prove “built” by itself — `verify_catalog.py` / CI must enforce the invariant above (strict mode); soft/dev runs may warn only per Section 9.4.

### 5.2 Environment (logical shape)

**Storage:** `registry/environments.yaml`


| Field                  | Required | Type / notes                                                                                     |
| ---------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| `id`                   | yes      | e.g. `main-rig`, `worker-rig`, `cloud-hosted`                                                    |
| `display_name`         | yes      | string                                                                                           |
| `purpose`              | yes      | short string                                                                                     |
| `runtime_class`        | yes      | enum: `local_main`, `local_worker`, `local_dev`, `cloud_hosted`, `ci_only`, `hybrid`             |
| `network_boundary`     | yes      | enum or string: `offline`, `lab_lan`, `internet`, `vpc`, …                                       |
| `data_classes_allowed` | yes      | string[] e.g. `public`, `internal`, `secret_ref_only`                                            |
| `machine_or_account`   | yes      | opaque descriptor: hostname pattern, account id, or `see_AGENTS_md` ref — **no secrets in repo** |
| `promotion_policy`     | yes      | string or enum: who may promote; reference to governance doc section                             |


### 5.3 Suggested capability keys (extensible)


| Key                | Typical meaning                          |
| ------------------ | ---------------------------------------- |
| `auth`             | Identity / authn-authz                   |
| `api`              | Machine-facing API surface               |
| `ui`               | Human-facing UI                          |
| `observability`    | Logs, metrics, traces                    |
| `approvals`        | Governance/approval integration          |
| `deployment`       | Repeatable deploy to at least one env    |
| `retrieval`        | RAG / document retrieval (if applicable) |
| `worker_execution` | Jobs on worker rig                       |
| `ingestion`        | Data/document ingestion pipelines        |


**Per-capability maturity enum:** `unbuilt`  `partial`  `built`  `na`

**Example `capabilities` block:**

```yaml
capabilities:
  auth: partial
  api: built
  ui: partial
  observability: unbuilt
  approvals: built
  deployment: partial
  retrieval: na
  worker_execution: na
  ingestion: built
```

**Roll-up rule (v1):** If any non-`na` capability is `unbuilt` or `partial`, `lifecycle_state` **must not** be `built` unless an explicit exception is recorded. Prefer fixing data over overrides.

**Lifecycle override guardrails (when `lifecycle_state` disagrees with the roll-up rule):** Overrides are **dangerous** if they become a routine bypass of capability/evidence rules. When used, **all** of the following are required:

1. **`lifecycle_override_reason`** — non-empty string on the component (why the roll-up is intentionally inconsistent).
2. **`approval_owner` review** — the PR that introduces or keeps the override must be reviewed by the component’s `approval_owner` (or documented delegate); implement as process + optional CODEOWNERS alignment.
3. **CI warning always** — `verify_catalog.py` (or CI) must **emit a visible warning** whenever `lifecycle_override_reason` is set, **even if** the change is merge-allowed. Silent overrides are forbidden.

Without (1)–(3), validators should **fail** the catalog (treat as invalid override).

### 5.4 Authority bindings

**Structure per domain:**

```yaml
authority:
  api_contract:
    source_kind: openapi
    canonical_ref: "repo:geomapper/backend/openapi.yaml@main"
    precedence: 1
  runtime_config:
    source_kind: secret_manager
    canonical_ref: "vault:lab/geomapper#runtime"
    precedence: 1
  deployment_topology:
    source_kind: terraform
    canonical_ref: "repo:infra/terraform/geomapper@main"
    precedence: 1
  operator_procedure:
    source_kind: runbook
    canonical_ref: "repo:geomapper/docs/runbooks/incident.md@main"
    precedence: 1
  implementation_behavior:
    source_kind: code
    canonical_ref: "repo:geomapper/backend@main"
    precedence: 1
```

**Domains (v1 minimum set):**


| Domain id                 | Meaning                               |
| ------------------------- | ------------------------------------- |
| `api_contract`            | External/API shape                    |
| `runtime_config`          | Env-specific configuration            |
| `deployment_topology`     | Where/how it runs                     |
| `operator_procedure`      | Human procedures                      |
| `implementation_behavior` | What the running system actually does |


**Source kinds (v1):** `openapi`, `code`, `terraform`, `railway_config`, `secret_manager`, `runbook`, `generated_artifact` (e.g. lockfile, SBOM pointer)

### 5.5 Environment deployment binding (on component)

```yaml
environments:
  main-rig:
    deployed: false
    notes: "Dev only"
  worker-rig:
    deployed: true
    runtime_role: primary
  cloud-hosted:
    deployed: false
```

### 5.6 Evidence model (first-class)

**Evidence storage strategy (locked):**


| Version | Where evidence results live                                                                                                                             | Notes                                                                                                                                          |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **v1**  | **Inline only** — inside each component’s `evidence` map in `registry/components.yaml` (`status`, `observed_at`, optional small embedded `last_result`) | Single pattern for all components; drift scripts **update these fields in place** or emit a PR patch. **No** `registry/evidence/*.json` in v1. |
| **v2+** | **Split** — e.g. `registry/evidence/<component_id>.json` for CI-generated, signed, or bulky attestations; component may **reference** by id             | Reduces YAML churn; supports signing.                                                                                                          |


Do **not** mix inline and external files per component in v1.

Each evidence entry should support:


| Subfield                 | Purpose                                                                                          |
| ------------------------ | ------------------------------------------------------------------------------------------------ |
| `type`                   | `artifact_registry`, `deployment`, `http_health`, `pipeline`, `repo_shape`, `manual_attestation` |
| `required_for_lifecycle` | bool — if true, failing this blocks claiming `built`                                             |
| `spec`                   | type-specific: e.g. image name pattern, URL, glob paths                                          |
| `last_result`            | v1: optional **embedded** summary only. v2+: may reference external attestation file             |
| `status`                 | `pass`, `fail`, `unknown`, `skipped`                                                             |
| `observed_at`            | ISO-8601                                                                                         |


**Example:**

```yaml
evidence:
  image_in_registry:
    type: artifact_registry
    required_for_lifecycle: true
    spec: { registry: "ghcr.io/lab/geomapper", tag_pattern: "semver" }
    status: unknown
    observed_at: null
  repo_has_openapi:
    type: repo_shape
    required_for_lifecycle: true
    spec: { repo_id: geomapper, paths: ["backend/openapi.yaml"] }
    status: unknown
    observed_at: null
```

**`last_verified_at` (component-level):** Max of `observed_at` for all `required_for_lifecycle` evidence, or explicit rollup from verification script.

---

## 6. Authority and conflict resolution

### 6.1 Domain → source kind

The catalog stores **which kind** is authoritative per domain. **Precedence** applies when two artifacts of **competing** kinds could apply to the **same** domain (rare if domains are well-scoped).

### 6.2 Precedence rules (normative for v1)

When sources disagree **within the same domain**:

1. **api_contract:** `openapi` beats prose docs; `generated_artifact` from OpenAPI beats hand-written duplicate specs.
2. **runtime_config:** `secret_manager` / sealed env beats committed `.env`; committed **templates** are non-authoritative for secret values.
3. **deployment_topology:** `terraform` or `railway_config` beats README diagrams; **actual cloud console** is operational truth only if captured as attested evidence, not as competing YAML in repo (avoid duplicating console state in two files).
4. **operator_procedure:** `runbook` beats chat logs; **implementation_behavior** (`code`) wins for *what runs*; runbook wins for *what humans are supposed to do* when the domain is `operator_procedure`.
5. **implementation_behavior:** `code` (merged `main`) wins over stale docs; if docs must override behavior, that is a **process** change (issue/PR), not a catalog fiction — catalog should point to code as authoritative for behavior.

**Cross-domain conflicts:** Not “resolved” by a single winner — e.g. API spec vs implementation: treat as **drift** between `api_contract` source and `implementation_behavior` (contract tests, breaking-change policy).

### 6.3 Examples


| Conflict                                                     | Resolution                                                                                     |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- |
| OpenAPI says field X; code omits X                           | Drift signal; implementation_behavior shows code; api_contract should be updated or code fixed |
| Runbook says restart order A; Terraform defines dependency B | deployment_topology authoritative for infra graph; runbook must align or cite exception        |
| README claims “deployed to prod”; evidence shows no deploy   | Catalog `environments` / evidence status must be updated; CI fails if `lifecycle_state: built` |


### 6.4 Global precedence table (v2+ refinement)

**v1:** Precedence is expressed **per binding** (e.g. `precedence: 1` on each `authority` entry) and by the normative bullets in Section 6.2. That is enough to ship.

**Future (recommended):** Introduce a single **`authority_rules`** document (e.g. `registry/authority_rules.yaml` or a top-level key in catalog bundle) mapping each **domain** to an ordered list of **source kinds** (first = wins within that domain when kinds conflict). Example shape:

```yaml
authority_rules:
  api_contract:
    precedence: [openapi, generated_artifact, code]
  runtime_config:
    precedence: [secret_manager, railway_config, code]
  deployment_topology:
    precedence: [terraform, railway_config, runbook]
  operator_procedure:
    precedence: [runbook, code]
  implementation_behavior:
    precedence: [code, generated_artifact]
```

Implementers should **not** build this in v1 unless needed; when added, per-component `authority` entries should **reference** or stay consistent with the global table (validator enforces agreement).

---

## 7. Verification model

### 7.1 Evidence types (v1)


| type                 | Collects                                             |
| -------------------- | ---------------------------------------------------- |
| `repo_shape`         | Paths/globs exist in cloned repo                     |
| `pipeline`           | Last workflow run conclusion (optional; needs token) |
| `artifact_registry`  | Image/package exists (optional; needs registry auth) |
| `deployment`         | K8s/Railway/HTTP smoke (optional)                    |
| `http_health`        | GET returns 200 (optional)                           |
| `manual_attestation` | Human JSON with signed-off timestamp (optional)      |


### 7.2 Collection

- **Phase 1–2:** Static: schema validate + `repo_shape` using `repo_registry.json` paths (main rig canonical only; Section 8.4).
- **Phase 3:** Optional networked checks behind env flags / CI secrets; never store secrets in catalog. Evidence results written **inline** into `components.yaml` (Section 5.6).

### 7.3 Drift meaning

Drift = declared state **or** required evidence **not satisfied** by observation (including stale `last_verified_at`).

### 7.4 Drift checks in v1

**Built invariant:** Mandatory checks below implement the **Section 4 hard invariant** (`required_for_lifecycle` → `pass` + `observed_at` within freshness window) for any component with `lifecycle_state: built`.


| Check                                                                             | Mode                                                              |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| JSON Schema validation for `components.yaml`, `environments.yaml`                 | **Mandatory**                                                     |
| Unique `id`s, valid `repo_id` references                                          | **Mandatory**                                                     |
| `lifecycle_state: built` ⇒ all `required_for_lifecycle` evidence `pass` and fresh | **Mandatory in strict CI**; **warn-only** on dev machine optional |
| Repo shape (paths)                                                                | **Mandatory** for seed components where spec is set               |
| Capability vs lifecycle consistency                                               | **Mandatory** (roll-up rule)                                      |
| Registry HTTP / K8s                                                               | **Optional** v1                                                   |


### 7.5 Mandatory vs optional (early rollout)

- **Mandatory:** schema, referential integrity (repo ids), repo_shape where `spec` filled, lifecycle/capability consistency.
- **Optional:** pipeline API, cloud deploy probes, artifact registry API — enable per environment when credentials exist.

---

## 8. Repository layout (Option A: extend ai-lab-governance)

### 8.1 Why Option A first

- Primary consumers are **agents, approvals, rig alignment** — same repo already versions [configs/governance_version.yaml](e:/Repos/ai-lab-governance/configs/governance_version.yaml) and [bootstrap/verify_governance.py](e:/Repos/ai-lab-governance/bootstrap/verify_governance.py).
- Shortest path to **one clone** on main + worker with matching catalog.
- **When to split to a separate repo:** non-governance owners need independent release cadence, external CI cannot access governance repo, or catalog size/compliance requires isolation. Then move `registry/components.yaml` + schemas + verify scripts and pin **version** from governance.

### 8.2 Proposed files


| Path                                                                                                | Purpose                                                                         |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| [schemas/component.schema.json](e:/Repos/ai-lab-governance/schemas/component.schema.json)           | JSON Schema for one component record                                            |
| [schemas/environment.schema.json](e:/Repos/ai-lab-governance/schemas/environment.schema.json)       | JSON Schema for one environment record                                          |
| [schemas/catalog_bundle.schema.json](e:/Repos/ai-lab-governance/schemas/catalog_bundle.schema.json) | Optional wrapper: root `components` + `environments` arrays                     |
| [registry/components.yaml](e:/Repos/ai-lab-governance/registry/components.yaml)                     | All components                                                                  |
| [registry/environments.yaml](e:/Repos/ai-lab-governance/registry/environments.yaml)                 | All environments                                                                |
| [registry/repo_registry.json](e:/Repos/ai-lab-governance/registry/repo_registry.json)               | Maps `repo_id` → filesystem path / URL; **linkage layer** to components         |
| [scripts/verify_catalog.py](e:/Repos/ai-lab-governance/scripts/verify_catalog.py)                   | Schema + integrity + lifecycle/capability rules                                 |
| [scripts/check_catalog_drift.py](e:/Repos/ai-lab-governance/scripts/check_catalog_drift.py)         | Evidence collection + drift vs declared; v1 updates **inline** evidence in YAML |
| `registry/evidence/`                                                                                | **v2+ only** — external attestations; **omit or empty in v1** (see Section 5.6) |


### 8.3 `repo_registry.json` linkage

Each component’s `primary_repo` / `related_repos` must equal a `repo_id` key in `repo_registry.json`:

```json
{
  "version": "1.0",
  "repos": [
    { "repo_id": "geomapper", "path": "E:/Repos/geomapper app", "repo_class_ref": "tooling_internal" }
  ]
}
```

**Note:** `repo_class_ref` is **informational linkage** to [policies/repo_classes.yaml](e:/Repos/ai-lab-governance/policies/repo_classes.yaml) — not duplication of class definition.

### 8.4 Repo paths: v1 rule (main rig canonical; worker out of scope)

**v1 is intentionally single-path:**


| Rule                | Detail                                                                                                                                                                                                                                  |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Canonical paths** | `repo_registry.json` lists **main rig** filesystem paths only (e.g. `E:/Repos/...`). This is the SSoT for `repo_shape` and local validation on the main machine.                                                                        |
| **Worker rig**      | Do **not** add alternate paths, per-machine overlays, or path arrays in v1. Worker-side truth uses **SSH / remote execution** and resolution on the worker (supervisor-approved commands), not a second column in `repo_registry.json`. |
| **Deferred**        | Multi-path maps, `paths_by_machine`, or worker-local clones in the registry are **post-v1** — they slow the first ship and duplicate truth.                                                                                             |


`check_catalog_drift.py` on the worker (if run there) either runs against paths **after** git clone to a known location on the worker (documented in runbook) or is **not** required on the worker for v1; main-rig CI remains authoritative for repo_shape against canonical paths.

---

## 9. Validation and CI

### 9.1 Schema validation

- Use JSON Schema Draft-07 (match existing [schemas/tool_registry.schema.json](e:/Repos/ai-lab-governance/schemas/tool_registry.schema.json) style).
- Validate YAML after parse to JSON structure in `verify_catalog.py`.

### 9.2 `verify_catalog.py` behavior

- Load `components.yaml`, `environments.yaml`, `repo_registry.json`.
- Validate schema; check foreign keys (`primary_repo`, `environment` ids).
- Enforce capability / `lifecycle_state` rules; enforce `built` evidence rules (strictness via env `CATALOG_STRICT=1`).

### 9.3 `check_catalog_drift.py` behavior

- Run `repo_shape` checks (resolve `path` from `repo_registry` — **main rig paths only**, Section 8.4).
- Update **`status` / `observed_at` / embedded `last_result`** inline in the component record (patch file or documented manual merge); v1 **does not** write `registry/evidence/*.json`.
- Exit non-zero on drift in strict mode.

### 9.4 CI failure behavior


| Condition                                                      | Merge blocking?                                                                                    |
| -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Schema invalid                                                 | Yes                                                                                                |
| Unknown repo id                                                | Yes                                                                                                |
| `lifecycle_state: built` with failed/missing required evidence | Yes in strict                                                                                      |
| Optional probe unreachable                                     | Warn or skip (config)                                                                              |
| Stale `last_verified_at`                                       | Warn in v1; block in strict later                                                                  |
| `lifecycle_override_reason` set                                | **Always warn** (non-blocking unless policy tightens); missing required override fields = **fail** |


### 9.5 `verify_governance.py` extension

- Add optional step: if `registry/components.yaml` exists, invoke `scripts/verify_catalog.py` (or document separate CI job). Avoid breaking rigs without Python deps — use `try/except` or explicit flag `AI_LAB_VERIFY_CATALOG=1`.

---

## 10. Agent safety / governance interaction

- Agents treat catalog as **read-mostly**; mutations require same approval path as other file edits.
- **Catalog changes are reviewable** — PR description should state what maturity/authority/ownership changed and why.
- **Governance does not subsume catalog:** policy files do not become the inventory; catalog does not encode allowlists (except cross-reference by id if ever needed).
- **Orchestrator read path:** load catalog read-only at start of task; use authority bindings to choose which file to trust for a domain.

---

## 11. Phased build order

### Phase 1 — Schema and stub records


| Item             | Detail                                                                                                                                                          |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**         | Runnable empty/skeleton catalog validated by schema                                                                                                             |
| **Files**        | `schemas/component.schema.json`, `schemas/environment.schema.json`, `registry/components.yaml`, `registry/environments.yaml`, seed `repo_registry.json` entries |
| **Deliverables** | Valid minimal YAML; documented enums in schema                                                                                                                  |
| **Acceptance**   | Manual run: validator passes on stubs                                                                                                                           |
| **Risks**        | Over-strict schema slows iteration — start with reasonable `additionalProperties` policy                                                                        |


### Phase 2 — Validation and CI wiring


| Item             | Detail                                                                                                            |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Goal**         | `verify_catalog.py` mandatory checks; CI/governance verify hook                                                   |
| **Files**        | `scripts/verify_catalog.py`, `verify_governance.py` optional integration, CI workflow if repo uses GitHub Actions |
| **Deliverables** | Exit codes documented; `CATALOG_STRICT` behavior                                                                  |
| **Acceptance**   | Failing PR if schema breaks                                                                                       |
| **Risks**        | Ensure `repo_registry` paths match **main rig** layout; worker has no alternate paths in v1 (Section 8.4)         |


### Phase 3 — Evidence and drift


| Item             | Detail                                                          |
| ---------------- | --------------------------------------------------------------- |
| **Goal**         | `check_catalog_drift.py`; repo_shape; `built` gating            |
| **Files**        | `scripts/check_catalog_drift.py` (no `registry/evidence/` in v1) |
| **Deliverables** | Seed components with real evidence specs                        |
| **Acceptance**   | Drift detected when path missing or lifecycle inconsistent      |
| **Risks**        | Network checks flaky — keep optional                            |


### Phase 4 — Generated docs/views


| Item             | Detail                                                                                          |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| **Goal**         | Single markdown or HTML summary from YAML                                                       |
| **Files**        | `scripts/generate_catalog_doc.py` (optional), output to `docs/` or `registry/README_catalog.md` |
| **Deliverables** | Human-readable table of components                                                              |
| **Acceptance**   | Doc regenerates deterministically from catalog                                                  |
| **Risks**        | Doc drift if generation not in CI                                                               |


### Phase 5 — Orchestrator / agent surfaces


| Item             | Detail                                                                                               |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| **Goal**         | Prompts or tools read catalog path from env; cite authority in answers                               |
| **Files**        | `cursor/prompts/*.txt` or wrapper pointers, [AGENTS.md](e:/Repos/ai-lab-governance/AGENTS.md) update |
| **Deliverables** | Documented `AI_LAB_CATALOG_ROOT` or implicit governance root                                         |
| **Acceptance**   | Agent can answer “what is authoritative for API X” from catalog                                      |
| **Risks**        | Overloading prompts — keep one short “catalog pointer” section                                       |


---

## 12. Initial seed entries


| Component id           | Why first                                                                                                        |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `ai-lab`               | Umbrella lab / tooling; establishes pattern for meta-components                                                  |
| `command-center`       | If this is your orchestration hub — central for agent behavior                                                   |
| `geomapper`            | Real application with API/UI/ingestion — exercises capability matrix                                             |
| `worker`               | Worker rig execution — `runtime_class` + `worker_execution` capability                                           |
| `secrets-config-plane` | Infra for secrets/config **without** storing secrets — authority `runtime_config` → `secret_manager` / path refs |


Each seed should include: minimal **authority** map, **ownership** axes, **environments** map (main-rig, worker-rig, cloud-hosted as applicable), **capabilities** realistic to current truth (honest `partial`/`unbuilt`), **evidence** starting with `repo_shape` only until Phase 3 expands.

---

## 13. V1 non-goals

- Full automatic discovery of all repos on disk
- **Per-machine or per-rig path maps** in `repo_registry.json` (worker-local paths as a second column, overlays, etc.) — v1 is main-rig canonical only (Section 8.4)
- **External evidence files** (`registry/evidence/*.json`) — v2+ (Section 5.6)
- Storing secret values or credentials in catalog
- Replacing `tool_registry.json` or merging tools into components (link only)
- Real-time health federation across all services
- Fine-grained RBAC inside YAML (governance policies remain separate)
- Multi-tenant catalog

---

## 14. Acceptance criteria (v1 complete)

1. `components.yaml` and `environments.yaml` validate against schemas in CI.
2. `repo_registry.json` lists all `repo_id`s referenced by seed components with **main-rig canonical paths** (Section 8.4); no worker-only path columns in v1.
3. `verify_catalog.py` enforces referential integrity and lifecycle/capability consistency.
4. `check_catalog_drift.py` runs repo_shape checks for seed components; documents exit codes.
5. Claiming `lifecycle_state: built` for any seed component either **fails** until evidence passes, or that component honestly stays `partial` until checks pass (no false “built”).
6. [AGENTS.md](e:/Repos/ai-lab-governance/AGENTS.md) or this plan’s sibling pointer documents where catalog lives and that agents must not silently edit it.
7. Governance files remain valid; `verify_governance.py` still passes baseline (with catalog verification optional or gated).
8. Evidence is **inline-only** in v1 (no split storage); any `lifecycle_override_reason` produces a **CI warning** and invalid overrides fail validation.

---

## 15. Future extensions

- **Separate catalog repo** when external teams or CI need independent versioning or governance repo access is constrained.
- **Dashboards** — consume YAML via static site or internal portal.
- **Orchestrator** — cache catalog; pass component id into jobs; auto-select runbooks from `authority.operator_procedure`.
- **Health federation** — periodic evidence writers; v2+ may push to `registry/evidence/` with signed attestations (Section 5.6).
- **`authority_rules.yaml`** — global precedence table (Section 6.4).

---

## Appendix A — Recommended file tree

```text
ai-lab-governance/
  CATALOG_SSOT_IMPLEMENTATION_PLAN.md   # this document
  schemas/
    component.schema.json
    environment.schema.json
    catalog_bundle.schema.json            # optional
  registry/
    components.yaml
    environments.yaml
    repo_registry.json                    # extended, not replaced
    # evidence/ omitted in v1 (v2+ external attestations)
  scripts/
    verify_catalog.py
    check_catalog_drift.py
    generate_catalog_doc.py               # Phase 4 optional
```

---

## Appendix B — Minimum viable schema field list

**Component:** `id`, `display_name`, `primary_repo`, `related_repos`, `component_type`, `lifecycle_state`, `capabilities`, `authority`, `code_owner`, `deploy_owner`, `runtime_owner`, `approval_owner`, `environments`, `evidence`, `last_verified_at`; optional `lifecycle_override_reason` (only with guardrails in Section 5.3)

**Environment:** `id`, `display_name`, `purpose`, `runtime_class`, `network_boundary`, `data_classes_allowed`, `machine_or_account`, `promotion_policy`

---

## Appendix C — Phase execution checklist

- Phase 1: Schemas + stub YAML + extend `repo_registry.json` with seed repo ids
- Phase 2: `verify_catalog.py` + CI + optional `verify_governance.py` hook
- Phase 3: `check_catalog_drift.py` + repo_shape + built gating
- Phase 4: Doc generation (optional)
- Phase 5: Prompt/AGENTS updates for read path
- v1 acceptance criteria (Section 14) all satisfied

---

## Appendix D — Open questions / assumptions

1. **Repo paths (resolved for v1):** `repo_registry.json` = **main rig canonical paths only**; worker uses SSH / remote resolution — **no multi-path mapping in v1** (Section 8.4). Per-machine overlays remain a **future** extension.
2. **Whether `command-center` maps to a concrete repo** in your workspace — confirm id and path before seeding.
3. **CI provider** for `ai-lab-governance` — if none, run `verify_catalog.py` locally in bootstrap docs until Actions exist.

---

**End of `CATALOG_SSOT_IMPLEMENTATION_PLAN.md` specification.**
