# Global Policy — ai-lab-governance

Single source of truth for **what** is allowed and **why**. Both Cursor and local AI must obey this. Enforcement is via wrappers and policy files, not prompts alone.

---

## 1. One source of truth

- **This repo** is the governance layer. Main rig and worker rig use the same clone (e.g. `E:\AI\ai-lab-governance\` or `E:\Repos\products\ai-lab-governance\` on main; `/opt/ai/ai-lab-governance/` on worker).
- Sync via Git. Both machines should run the same **governance version** (see `configs/governance_version.yaml`). Bootstrap verifier ensures alignment.

---

## 2. Trust tiers (approval)

| Tier | Meaning |
|------|--------|
| **T0** | Read-only. No state changes. |
| **T1** | Draft only. Propose; do not apply. |
| **T2** | Approval required. Propose → human/system approval → execute. |
| **T3** | Allowlisted autonomy. In allowed scopes only. |
| **T4** | Managed free rein in narrow, documented scopes. |

State-changing actions (file edit, script run, service restart, config change, dependency install, registry update, memory write) go through approval or allowlist. See `policies/approval_tiers.yaml` and `policies/allowlists.yaml`.

---

## 3. What is always denied

- SSH config edits, firewall changes, unrestricted root/sudo.
- Reading or writing secret files outside approved scopes.
- Bypassing wrappers (no direct state-changing shell from the model).

Defined in `policies/denied_actions.yaml`. No exceptions without a formal policy change in this repo.

---

## 4. Tool registry is mandatory

- Before running or creating scripts: **look up** `registry/tool_registry.json`.
- If a tool exists → use it (and log).
- If not → require approval to create or adapt; then register if promoted to official.
- “Reuse first, generate last.” Temporary tools stay unregistered until promoted.

---

## 5. Logging

- Every meaningful AI action is logged via `wrappers/log_action.py` (or equivalent).
- Required fields: timestamp, machine, agent, user_request_id, action_id, target repo/path, approval_tier, wrapper_used, result, rollback_reference if applicable.
- Schema: `schemas/action_log.schema.json`. Logs are read-only for agents (except the logger).

---

## 6. Memory rules

- Raw feedback is not permanent memory. Candidate memory requires repeated confirmation or explicit “remember this.”
- Permanent memory promotion: explicit scope, reversibility, and log entry. No silent promotion.
- Trust changes always require approval. See `policies/memory_rules.yaml`.

---

## 7. Cursor and local AI

- **Cursor:** Repo-level `AGENTS.md` in every project comes from `templates/repo_AGENTS_template.md`. Cursor rules and prompts live in `cursor/`; bootstrap installs them so both rigs behave the same.
- **Local AI:** Does not execute tools directly. Flow: Model → Supervisor → Approved wrapper → System. Wrappers read policy files and registry; they enforce approval and logging.

---

## 8. Cross-machine SSH standard

- **Canonical worker SSH target:** `worker@worker-node`
- **Who uses SSH:** Only the orchestrator/supervisor layer initiates SSH to the worker. Individual agents in Cursor or the local model do **not** call `ssh` directly; they route requests through the supervisor / approved wrappers.
- **Allowed pattern:** `ssh worker@worker-node "<approved-command>"` where `<approved-command>` is either:
  - a read-only status/check command that passes `policies/denied_actions.yaml`, or
  - a wrapper-backed command on the worker that itself enforces policy (e.g. a worker-side `run_approved` or safe status script).
- **No direct sudo/root over SSH:** SSH sessions must use restricted users and approved commands only. No interactive shells, no uncontrolled port forwarding, no `sudo` without an explicit wrapper/policy.

Document any additional worker aliases or alternative hostnames in repo-level `AGENTS.md` when they differ from `worker@worker-node`.

---

## 9. Enforcement stack (layers)

1. **Governance repo** — Human- and machine-readable source of truth.
2. **Bootstrap scripts** — Install same rules/config on both rigs.
3. **Supervisor** — Control plane; all AI actions go through it.
4. **Approved wrappers** — Only path for state changes.
5. **Logs and approval records** — Auditable and reversible.

---

## 10. Version and drift

- `configs/governance_version.yaml` holds `governance_version` (e.g. `0.3.2`).
- `bootstrap/verify_governance.py` checks: repo present, required files, policy hashes (optional), Cursor rules installed, wrappers present, registry readable, logs/approval paths exist.
- If verification fails, the rig is not considered governed; fix before relying on automation.

---

## 11. New projects

- New repos must not start blank. Initialize with: AGENTS.md (from template), .cursorignore, pointer to governance repo version, and logging/approval wrapper config. Use `templates/project_init_checklist.md`.
