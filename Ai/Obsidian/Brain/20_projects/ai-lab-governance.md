---
project_name: ai-lab-governance
type: core-project
status: active
created: 2026-05-28
updated: 2026-05-28
---

# ai-lab-governance

## Overview
Shared control plane for Cursor + local AI: policies, registries, schemas, wrappers, bootstrap, version pins for both rigs.

## Key Areas

- `policies/` — approval tiers, allowlists, execution rules
- `registry/` — tool/repo/agent registry JSON
- `schemas/`, `wrappers/`, `bootstrap/`

## Project Notes
<!-- Add links to project-specific notes as they are created -->
- [[20_projects/ai-lab-governance/approvals|approvals]]
- [[20_projects/ai-lab-governance/bootstrap|bootstrap]]
- [[20_projects/ai-lab-governance/configs|configs]]
- [[20_projects/ai-lab-governance/cursor|cursor]]
- [[20_projects/ai-lab-governance/logs|logs]]
- [[20_projects/ai-lab-governance/policies|policies]]
- [[20_projects/ai-lab-governance/registry|registry]]
- [[20_projects/ai-lab-governance/schemas|schemas]]
- [[20_projects/ai-lab-governance/scripts|scripts]]
- [[20_projects/ai-lab-governance/templates|templates]]
- [[20_projects/ai-lab-governance/wrappers|wrappers]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Vault
- [[Brain Home]]
- [[20_projects/index|All projects]]

## Repo Structure




<!-- REPO_STRUCTURE_START -->
|-- approvals
|   |-- approved
|   |-- denied
|   +-- proposals
|-- bootstrap
|   |-- setup_main_rig.ps1
|   |-- setup_worker_rig.ps1
|   |-- setup_worker_rig.sh
|   +-- verify_governance.py
|-- configs
|   +-- governance_version.yaml
|-- cursor
|   |-- prompts
|   |   |-- business_tooling_system.txt
|   |   |-- orchestrator_system.txt
|   |   +-- worker_system.txt
|   |-- cursor_rules.md
|   +-- cursorignore_template
|-- logs
|   +-- actions
|-- policies
|   |-- allowlists.yaml
|   |-- approval_tiers.yaml
|   |-- denied_actions.yaml
|   |-- execution_rules.yaml
|   |-- memory_rules.yaml
|   +-- repo_classes.yaml
|-- registry
|   |-- agent_registry.json
|   |-- components.yaml
|   |-- environments.yaml
|   |-- README_catalog.md
|   |-- repo_registry.json
|   +-- tool_registry.json
|-- schemas
|   |-- action_log.schema.json
|   |-- approval_request.schema.json
|   |-- catalog_bundle.schema.json
|   |-- component.schema.json
|   |-- environment.schema.json
|   |-- job.schema.json
|   |-- memory_event.schema.json
|   +-- tool_registry.schema.json
|-- scripts
|   |-- check_catalog_drift.py
|   |-- generate_catalog_doc.py
|   |-- requirements-catalog.txt
|   +-- verify_catalog.py
|-- templates
|   |-- approval_request_example.json
|   |-- project_init_checklist.md
|   +-- repo_AGENTS_template.md
|-- wrappers
|   |-- log_action.py
|   |-- read_registry.py
|   |-- run_approved.py
|   |-- safe_exec.py
|   +-- submit_approval.py
|-- .gitignore
|-- AGENTS.md
|-- CATALOG_SSOT_IMPLEMENTATION_PLAN.md
|-- GLOBAL_POLICY.md
+-- README.md
<!-- REPO_STRUCTURE_END -->

## Change Log
<!-- CHANGELOG_START -->
<!-- CHANGELOG_END -->

## Related
- [[20_projects/index|Projects Index]]
- [[20_projects/ai-lab|ai-lab]]
