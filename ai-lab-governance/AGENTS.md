# ai-lab-governance — Agent Contract

**Role:** Shared control repo for Cursor and local AI. Both main rig and worker rig pull from this repo. This is the enforcement layer: behavior, permissions, allowlists, approval rules, logging, registry lookups, memory rules.

**Source of truth:** GLOBAL_POLICY.md and policies/*.yaml. When in conflict, GLOBAL_POLICY.md wins.

## Rules for any agent (Cursor or local AI)

1. **Use tool registry first** — Before creating or running scripts, check `registry/tool_registry.json`. Reuse existing tools; create new only when none exist and approval allows.
2. **Do not create new scripts if an existing one can be reused** — Adapt or compose existing tools. Register and document anything promoted to official.
3. **State-changing actions require approval unless allowlisted** — All file edits, script execution, service restarts, config changes, etc. go through approval or must be in `policies/allowlists.yaml`. Use wrappers: `run_approved.py`, `submit_approval.py`, `safe_exec.py`.
4. **All actions must be logged** — Use `wrappers/log_action.py` (or equivalent) for every meaningful action. Required: timestamp, machine, agent, request id, action id, target, approval tier, result.
5. **Do not edit secrets/config outside approved scopes** — Secrets and security-sensitive config are in `policies/denied_actions.yaml`. No direct edits to SSH, firewall, or secret files.
6. **Use approved wrappers only** — No direct shell execution for state changes. Model → Supervisor → Wrapper → System.
7. **Keep files small and domain-grouped** — Under ~300 lines where possible; names that say what they do; group by feature/domain.
8. **Update docs when behavior changes** — If you change policy, wrappers, or registry, update GLOBAL_POLICY.md or relevant policy files and templates.

## Repo layout (quick ref)

- **AGENTS.md** — This file; repo contract.
- **GLOBAL_POLICY.md** — Human-readable policy; the “what and why.”
- **cursor/** — Cursor rules and prompts; bootstrap copies these to Cursor config.
- **policies/** — approval_tiers, allowlists, denied_actions, memory_rules, repo_classes, execution_rules (YAML).
- **registry/** — tool_registry.json, repo_registry.json, agent_registry.json, **components.yaml**, **environments.yaml** (system catalog), README_catalog.md (generated summary).
- **schemas/** — approval_request, action_log, job, memory_event, **component**, **environment**, **catalog_bundle** (catalog JSON Schema).
- **wrappers/** — run_approved.py, submit_approval.py, log_action.py, read_registry.py, safe_exec.py.
- **bootstrap/** — setup_main_rig.ps1, setup_worker_rig.ps1/.sh, verify_governance.py.
- **scripts/** — verify_catalog.py, check_catalog_drift.py, generate_catalog_doc.py (catalog tooling; see System catalog below).
- **templates/** — repo_AGENTS_template.md, project_init_checklist.md, approval_request_example.json.
- **configs/** — governance_version.yaml (version both rigs must match).

## System catalog (inventory SSoT)

Governance (policy, tiers, tool registry, repo **risk** classes) is separate from the **system catalog**: what components exist, capability maturity, authority bindings, ownership axes, environments, and inline evidence. Canonical files: `registry/components.yaml`, `registry/environments.yaml`, `registry/repo_registry.json` (main-rig paths only in v1). Specification: `CATALOG_SSOT_IMPLEMENTATION_PLAN.md`.

- **Read path:** Use the catalog for “what exists,” “what is authoritative for domain X,” and “who owns code/deploy/runtime.” Do not conflate with `policies/repo_classes.yaml` (automation risk).
- **Writes:** Catalog data is high-impact — same approval and PR rules as other governance edits; **no silent or unreviewed mutation** by agents.
- **Validation:** `pip install -r scripts/requirements-catalog.txt` then `python scripts/verify_catalog.py`. Strict CI-style checks: `CATALOG_STRICT=1`. Optional hook: `AI_LAB_VERIFY_CATALOG=1 python bootstrap/verify_governance.py`. Repo shape drift (main rig): `python scripts/check_catalog_drift.py` (on CI use `CATALOG_SKIP_REPO_SHAPE=1` when paths are Windows-only). Regenerate summary: `python scripts/generate_catalog_doc.py`.

`AI_LAB_CATALOG_ROOT` is not required when the catalog lives in this repo; use `AI_LAB_GOVERNANCE_ROOT` for scripts.

## Bootstrap and verification

- **Install rules on this machine:** Run `bootstrap/setup_main_rig.ps1` (Windows) or `bootstrap/setup_worker_rig.sh` (Linux worker).
- **Verify alignment:** Run `bootstrap/verify_governance.py`. Must pass before treating the rig as governed. On the main rig, optional stricter catalog gate: `AI_LAB_VERIFY_CATALOG=1 CATALOG_STRICT=1 python bootstrap/verify_governance.py`.

## Hard rule

**No local AI or Cursor-driven automation may perform a state-changing action except through the governance wrappers and policy files defined in this repo.**

Secrets and credentials are never stored in this repo. Document paths and env in runbooks or AGENTS.md of the lab that uses this governance repo.
