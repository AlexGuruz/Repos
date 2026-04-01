# Cursor rules — governed by ai-lab-governance

These rules apply when working in any repo that points to this governance layer. Same behavior on main rig and worker rig.

## Behavior

1. **Registry first** — Before creating or running a script, check the project’s tool registry (or `ai-lab-governance/registry/tool_registry.json`). Reuse existing tools; create new only when none exist and policy allows.
2. **No state change without approval or allowlist** — File edits, script execution, service restarts, config changes: use governance wrappers (run_approved, submit_approval, safe_exec) or confirm the action is allowlisted. Do not bypass.
3. **Log actions** — Meaningful actions must be logged (timestamp, agent, action, target, result). Use the project’s or governance log_action wrapper.
4. **Secrets** — Never hardcode secrets. Do not edit SSH config, firewall, or secret files unless explicitly allowlisted and through the approval path.
5. **Docs** — When behavior or config changes, update AGENTS.md, README, or runbooks as appropriate.
6. **Small, focused files** — Prefer files under ~300 lines; group by domain; names that describe purpose.

## Repo contract

- Repo root must have AGENTS.md (from governance template if new project).
- Follow repo-level AGENTS.md for build, test, conventions, and where config/secrets live.

## Governance repo path

If the workspace includes the governance repo, reference it for:
- `policies/approval_tiers.yaml`, `allowlists.yaml`, `denied_actions.yaml`
- `registry/tool_registry.json`
- `wrappers/run_approved.py`, `log_action.py`, `submit_approval.py`

If not in workspace, assume same policies apply and use wrappers from the configured governance path (e.g. E:\AI\ai-lab-governance\ or /opt/ai/ai-lab-governance\).
