# ai-lab-governance

Shared control repo for **Cursor** and **local AI** across main rig and worker rig. One source of truth for behavior, permissions, allowlists, approval rules, logging, registry lookups, and memory rules.

## Quick start

1. **Clone** to the same path on both machines, e.g.  
   - Main: `E:\Repos\products\ai-lab-governance\` or `E:\AI\ai-lab-governance\`  
   - Worker: `/opt/ai/ai-lab-governance/`
2. **Set env** (persist in profile):  
   - `AI_LAB_GOVERNANCE_ROOT` = path to this repo  
   - On worker: `AI_LAB_MACHINE=worker`
3. **Bootstrap**  
   - Main (Windows): `.\bootstrap\setup_main_rig.ps1`  
   - Worker (Linux): `./bootstrap/setup_worker_rig.sh /opt/ai/ai-lab-governance`  
   - Worker (Windows): `.\bootstrap\setup_worker_rig.ps1`
4. **Verify**: `python bootstrap/verify_governance.py` (must pass).

## Repo layout

| Path | Purpose |
|------|--------|
| **AGENTS.md** | Repo contract for agents |
| **GLOBAL_POLICY.md** | Human-readable policy (what and why) |
| **configs/governance_version.yaml** | Version both rigs must match |
| **cursor/** | Cursor rules and system prompts (bootstrap installs these) |
| **policies/** | approval_tiers, allowlists, denied_actions, memory_rules, repo_classes, execution_rules |
| **registry/** | tool_registry.json, repo_registry.json, agent_registry.json |
| **schemas/** | approval_request, action_log, job, memory_event (JSON Schema) |
| **wrappers/** | run_approved.py, submit_approval.py, log_action.py, read_registry.py, safe_exec.py |
| **bootstrap/** | setup_main_rig.ps1, setup_worker_rig.ps1/.sh, verify_governance.py |
| **templates/** | repo_AGENTS_template.md, project_init_checklist.md, approval_request_example.json |

## Hard rule

**No local AI or Cursor-driven automation may perform a state-changing action except through the governance wrappers and policy files defined in this repo.**

## Minimum viable (first 7)

1. This repo (clone on both rigs)  
2. **AGENTS.md** / **templates/repo_AGENTS_template.md** in every project  
3. **registry/tool_registry.json** — mandatory lookup before creating/running tools  
4. **policies/approval_tiers.yaml** — what needs approval  
5. **wrappers/run_approved.py** — only approved execution path  
6. **wrappers/log_action.py** — every action logged  
7. **bootstrap/verify_governance.py** — both rigs aligned  

## Sync and version

- Keep both machines on the same Git ref (tag or commit).  
- Bump `configs/governance_version.yaml` when you change policy or wrappers.  
- Run `verify_governance.py` after pull to ensure nothing is missing.

## Cursor .cursorignore

If `.cursorignore` in `cursor/` could not be created (e.g. permission), copy the list from **cursor/cursor_rules.md** or maintain a project-level `.cursorignore` that ignores secrets, `node_modules`, logs, and env files.

---

Aligned with **AI_LAB_GOAL_AND_PHILOSOPHY.md** (ai-lab) and the enforcement stack: governance repo → bootstrap → supervisor → wrappers → logs/approvals.
