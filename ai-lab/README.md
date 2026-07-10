# AI Lab

Multi-rig AI operations system: main rig (orchestration + governance) and worker rig (scan/compute tasks) coordinated over SSH.

## Documentation baseline

Use these files as canonical source of truth before changing any other docs:

- `docs_source/DOCUMENTATION_STANDARD.md` - uniform standards, precedence, and handoff rules
- `docs_source/WORKER_CURRENT.md` - active worker host, SSH identity, Ollama endpoint
- `docs_source/SSH_SETUP.md` - main-to-worker SSH setup and validation
- `docs_source/REPO_MIRROR.md` - repo mirror location and path conventions
- `docs_source/contracts/` - runtime contracts for execution, registry, memory, policy, and worker handoff
- `command-center/command-center/README.md` - command center runtime + env contract

## Current constants (synced)

- **Primary worker:** `gregw@power-1` (worker_assistant, n8n, Kylo — no Ollama)
- **GPU worker:** `worker@worker-node` — Ollama `http://worker-node:11434` (tunnel on acheron `:11435`)
- **Main rig Ollama:** `http://127.0.0.1:11434` (local on acheron)
- **Main repo root:** `E:\Repos\ai-lab`

## Operating principles

- **Reuse first:** prefer `registry/scripts.json` and existing workflows before new code.
- **High observability, low authority:** agents read state; writes/exec are policy-gated.
- **Structured memory:** persisted behavior lives in `memory/*.json` and `policy/*.yaml`.

## Quick start

1. From repo root: `cd E:\Repos\ai-lab`
2. **Command Center (recommended operator UI + API):** `.\scripts\start.ps1 -LocalOnly` — then open **http://localhost:5173** (API **http://127.0.0.1:8000**). Stop: `.\scripts\stop.ps1`. Full doc: `command-center/command-center/BOOT.md`.
3. CLI orchestrator: `python -m brain.orchestrator.main "sales today"`
4. Chat UI: `pip install flask` then `python -m chat_ui.app` (open `http://127.0.0.1:5000`)
5. Health snapshot: `python observability/collect_health.py` (writes `observability/health.json`)
6. Worker reachability check: `.\scripts\worker_ai\validate_m1_checklist.ps1 -WorkerIP worker-node`

## Testing

Core tests are in `tests/`. Run from repo root: `python -m pytest tests/ -v` (requires `pytest`). See `TESTING.md` for the full harness (ai-lab + command-center backend).

## Layout

- `brain/` - orchestrator, execution, approvals, planning
- `agents/` - specialized agents (cartographer, librarian, docsync, etc.)
- `registry/` - scripts, repos, integrations, workflows, services
- `memory/` - preferences, trust rules, workflow memory, project state
- `policy/` - autonomy tiers + allow/block lists
- `observability/` - health and status artifacts (collector writes, agents read)
- `docs_source/contracts/` - cross-system interface contracts
- `command-center/command-center/` - operator UI + API
