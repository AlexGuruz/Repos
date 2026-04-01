# AGENTS.md — [Project name]

**Governance:** This repo follows ai-lab-governance. Same behavior on main rig and worker rig.

## Rules for agents (Cursor and local AI)

1. **Use tool registry first** — Before creating or running scripts, check the lab tool registry (or this repo’s registry). Reuse existing tools; create new only when none exist and approval allows.
2. **No state-changing action without approval or allowlist** — File edits, script execution, config changes: use governance wrappers (`run_approved`, `submit_approval`, `safe_exec`) or confirm the action is allowlisted.
3. **Log actions** — Meaningful actions must be logged (timestamp, agent, action, target, result).
4. **Secrets** — Never hardcode. Do not edit SSH/firewall/secret files unless allowlisted and through approval. Config and secret paths: [document here or “see README”].
5. **Docs** — When behavior or config changes, update this file or README.
6. **Small, focused files** — Prefer under ~300 lines; group by domain; names that describe purpose.

## Repo layout (brief)

- [List key dirs: e.g. `src/`, `configs/`, `scripts/`, `docs/`]
- Secrets / env: [path or “see README”]
- Tool registry: [path to tool_registry.json or “use lab governance registry”]

## Build / test

- [How to build and run tests, e.g. `npm run build`, `pytest`]

## Governance repo path

- Main/worker: `E:\AI\ai-lab-governance\` or `E:\Repos\ai-lab-governance\` (main), `/opt/ai/ai-lab-governance/` (worker). Set `AI_LAB_GOVERNANCE_ROOT` to this path.

## Worker SSH (standard)

- Canonical worker target: `worker@worker-node`
- Individual agents should **not** call `ssh` directly; they route work to the orchestrator/supervisor, which uses this SSH target under governance wrappers.
- If this project needs different worker hosts, document them here explicitly.

---

*Generated from ai-lab-governance/templates/repo_AGENTS_template.md. Customize the bracketed sections for this project.*
