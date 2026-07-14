# Operator Desk (`operator_desk`)

Thin AI Lab package for primed Jobs, fast Growflow/email/pending/repo reads, and **approval-gated** writes.

**Import name:** `operator_desk` (not `operator` — avoids shadowing Python’s stdlib `operator`).  
**Contracts:** `docs/operator_desk_refinement/` (v1).  
**Principle:** High observability, low authority.

## Quick start

```powershell
cd E:\Repos\ai-lab
$env:PYTHONPATH = "."
$env:OPERATOR_DESK_ENABLED = "1"
python -m pytest operator_desk/tests -q
```

## Public API

| Symbol | Purpose |
|--------|---------|
| `get_settings()` | Cached settings (env + YAML) |
| `load_job_primer(job_id)` | Bounded Job note + tool hints |
| `resolve_job_id_for_message(message)` | Intent → job_id |
| `get_growflow_status()` | Snapshot-first status (no refresh) |
| `fetch_unread_digest(...)` | Gmail unread digest (auth required for live) |
| `list_pending_approvals()` | Brain queue pending view |
| `submit_tool_proposal(...)` | Allowlisted `scripts.json` proposal only |
| `get_repo_map_summary(...)` | Bounded registry summary |

## Layout

```
operator_desk/
  paths.py
  settings.py
  models.py
  errors.py
  job_primer.py
  intent_map.py
  approvals.py
  config/
  tools/
  api/
  tests/
```

## Safety (frozen)

- Writes: brain `approval-N` + `tool_name`/`args` → events execute → `brain.execution.run`
- Allowlist: `ai-lab/registry/scripts.json`
- Growflow: prepared snapshot + GET only — **never** `POST /api/retail/refresh`
- No Kylo writes; no raw shell; localhost-only HTTP when mounted

## Feature flag

`OPERATOR_DESK_ENABLED=1` required for HTTP router mount (Integration Gate 4). Library imports work without the flag.
