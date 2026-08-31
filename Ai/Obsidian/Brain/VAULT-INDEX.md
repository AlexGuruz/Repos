---
status: active
project: meta
type: index
---

# VAULT INDEX

Read this at the start of Operator Desk work. Load only the Job note needed for the task — do not dump the whole vault.

## Vault location

`E:\Repos\Ai\Obsidian\Brain` (override with `OPERATOR_BRAIN_VAULT_ROOT` / `BRAIN_VAULT_ROOT`).

## Who I Am (ops profile)

Operator of Acheron / Repos AI Lab stack: company email, Growflow retail visibility, governance-approved machine actions, repo awareness. Personal biography optional — keep secrets out of this file.

## Key systems

- **AI Lab Command Center** — chat + approvals (`127.0.0.1:8000`)
- **Growflow retail API** — `127.0.0.1:8791` via CC `/api/retail/*`
- **Operator Desk** — package `operator_desk` (primed Jobs + tools)
- **Governance** — `ai-lab-governance` wrappers + `scripts.json` allowlist

## Vault structure (map only)

```
10_runbooks     ← how-to / runbooks
20_projects     ← project mirrors (Growflow, Kylo, ai-lab, …)
30_infra        ← hosts, docker, watchers
40_operator     ← Operator Desk Jobs (AI priming)
_ops            ← ops notes / telemetry
```

Human project MOC: [[Brain Home]]

## What's active

See [[Active Priorities]].

## Operator Jobs (prime before domain work)

| Job | Note |
|-----|------|
| company_email | [[40_operator/jobs/job_company_email]] |
| growflow_retail | [[40_operator/jobs/job_growflow_retail]] |
| machine_actions | [[40_operator/jobs/job_machine_actions]] |
| repo_awareness | [[40_operator/jobs/job_repo_awareness]] |

## Rules for AI

1. Prefer prepared context / registered reads before LLM freeform.
2. State changes only via brain approval queue with `tool_name` + `args` from `scripts.json`.
3. Never raw shell. Never Kylo posting/runtime changes from Operator Desk.
4. Growflow: snapshot or GET status only — never `POST /api/retail/refresh` from Desk.
5. Do not send email in MVP; draft = proposal then approve.
6. Bound context — follow Job notes, not whole Repos.
