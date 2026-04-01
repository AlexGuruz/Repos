# Current worker rig

Single source of truth for the active worker used by scripts and docs.

| Item | Value |
|------|--------|
| **SSH** | `worker@worker-node` |
| **Hostname** | `worker-node` |
| **Ollama** | `http://worker-node:11434` (port 11434) |

## Contract

- Any doc that references worker identity must use values from this file.
- If worker host or account changes, update this file first, then sync dependent docs.
- Do not hard-code alternate worker usernames in other docs unless marked as legacy.

## Validation

- **M1 (Ollama reachable):** From main rig or from worker:  
  `.\scripts\worker_ai\validate_m1_checklist.ps1 -WorkerIP worker-node`
- **SSH:** `ssh worker@worker-node "echo ok"`

Use `worker-node` (or the worker’s LAN IP) wherever scripts or config need the worker host.
