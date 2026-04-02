# New project init checklist (governance)

Do not start new repos blank. Use this checklist so Cursor and local AI behave the same on both rigs.

## 1. Repo root

- [ ] **AGENTS.md** — Copy from `ai-lab-governance/templates/repo_AGENTS_template.md` and fill in project name, layout, build/test, secret paths.
- [ ] **.cursorignore** — Copy from `ai-lab-governance/cursor/.cursorignore` (or create one) and add project-specific ignores (e.g. `node_modules/`, `*.env`).
- [ ] **Pointer to governance** — Document governance repo path and that `AI_LAB_GOVERNANCE_ROOT` should point to it. Optionally add `governance_version` from `configs/governance_version.yaml`.

## 2. Logging and approval

- [ ] **Logging** — Ensure agents use the governance `log_action` wrapper (or equivalent) for meaningful actions. Document log path if different from governance `logs/actions/`.
- [ ] **Approval** — State-changing actions use `submit_approval` and `run_approved` (or allowlisted scope). Document any repo-specific allowlist in governance `policies/allowlists.yaml` or in AGENTS.md.

## 3. Registry

- [ ] **Tool registry** — If this repo has official scripts, register them in the lab `registry/tool_registry.json` (or project-specific registry and document in AGENTS.md).
- [ ] **Reuse first** — AGENTS.md states: use tool registry first; do not create new scripts if an existing one can be reused.
- [ ] **System catalog** — If the project is a tracked lab component, add or update `repo_id` in governance `registry/repo_registry.json` and a component entry in `registry/components.yaml` (see `CATALOG_SSOT_IMPLEMENTATION_PLAN.md` in ai-lab-governance).

## 4. Bootstrap (per machine)

- [ ] **Main rig** — Run `bootstrap/setup_main_rig.ps1` (or set `AI_LAB_GOVERNANCE_ROOT` and install Cursor rules).
- [ ] **Worker rig** — Run `bootstrap/setup_worker_rig.ps1` or `bootstrap/setup_worker_rig.sh` and set `AI_LAB_MACHINE=worker`.
- [ ] **Verify** — Run `bootstrap/verify_governance.py`; must pass.

## 5. Hard rule

**No local AI or Cursor-driven automation may perform a state-changing action except through the governance wrappers and policy files defined in the shared governance repo.**

---

*Source: ai-lab-governance/templates/project_init_checklist.md*
