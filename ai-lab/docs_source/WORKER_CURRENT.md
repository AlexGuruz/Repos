# Current worker rig

Single source of truth for the active worker used by scripts and docs.

| Item | Value |
|------|--------|
| **Primary worker SSH** | `gregw@power-1` |
| **Primary hostname** | `power-1` (Tailscale `100.77.230.81`) |
| **Primary tunnel ports (acheron)** | worker_assistant `:8765`, n8n `:5678` |
| **Secondary worker SSH** | `worker@worker-node` (Tailscale `100.99.177.106`; GPU / heavy workloads) |
| **Secondary tunnel ports (acheron)** | worker_assistant `:8766`, n8n `:5679`, GPU Ollama `:11435` → worker-node `:11434` |
| **Main rig SSH** | `zacle@acheron` (Tailscale `100.71.161.10`) |
| **Main rig Ollama** | `http://127.0.0.1:11434` (local on acheron — not tunneled) |
| **Kylo root (power-1)** | `C:\Project-Kylo` → junction to `C:\worker\repos\Project-Kylo` |
| **Gigatt root (power-1)** | `C:\Project-Kylo-Gigatt` (migrated from worker-node) |
| **Kylo code sync** | `.\scripts\sync_kylo_code_worker_node_to_power1.ps1` (worker-node live `C:\Project-Kylo` is source) |
| **Tunnel config** | `scripts/worker_tunnels.local.json` |
| **Setup** | `.\scripts\setup_power1_primary_worker.ps1` |
| **Verify** | `.\scripts\verify_power1_production.ps1` (use `:8765` now) |

## Ollama (where models run)

| Machine | Ollama | Endpoint from acheron |
|---------|--------|------------------------|
| **acheron** (main rig) | **Yes** — local GPU/CPU | `http://127.0.0.1:11434` |
| **worker-node** (GPU worker) | **Yes** — GPU models | `http://127.0.0.1:11435` (tunnel) or `http://worker-node:11434` (LAN) |
| **power-1** | **No** — iGPU mini PC | Do not install or tunnel Ollama here |

Use **acheron** for main-rig chat/dev models and **worker-node** for GPU-heavy inference. **power-1** runs worker_assistant, n8n, and Kylo Docker only.

## power-1 services (local)

| Service | Port | Boot |
|---------|------|------|
| worker_assistant | 8765 | `AiLabWorkerAssistant` + supervisor |
| n8n | 5678 | supervisor `n8n_daemon` |
| Kylo Docker | 5433/5434/5436, 9092, 8080, 6379 | Docker `kylo-watcher-2026` + `gigatt-kylo-watcher` only (**2025 complete — no host watcher**) |
| Supervisor | — | `AiLabWorkerSupervisor` at logon |

Governance: `AI_LAB_GOVERNANCE_ROOT=C:\Users\gregw\ai-lab`, `AI_LAB_MACHINE=worker`, `AI_LAB_ENFORCEMENT=1`

## worker-node services (local)

| Service | Port | Notes |
|---------|------|-------|
| worker_assistant | 8765 | Secondary tunnel on acheron `:8766` |
| n8n | 5678 | Secondary tunnel on acheron `:5679` |
| **Ollama** | **11434** | GPU models; tunnel on acheron `:11435` |

## Contract

- Any doc that references worker identity must use values from this file.
- **worker-node** hosts GPU Ollama. **acheron** hosts main-rig Ollama. **power-1** does not run Ollama.
- **worker-node** is reserved for GPU-heavy jobs; Kylo was migrated to **power-1** (2026-06-14). worker-node `Kylo Auto-Start` is disabled.
- If worker host or account changes, update this file first, then sync dependent docs.

## Surveillance (Blue Iris)

Interactive setup runbook (28 Amcrest cams, 12 TB on power-1, TVs on worker-node, mobile via UI3): [BLUE_IRIS_SURVEILLANCE_SETUP.md](./BLUE_IRIS_SURVEILLANCE_SETUP.md)

## Validation

- **SSH:** `ssh gregw@power-1 "echo ok"`
- **Primary worker (from acheron):** `curl.exe http://127.0.0.1:8765/health`
- **Main-rig Ollama:** `curl.exe http://127.0.0.1:11434/api/tags`
- **GPU Ollama (worker-node via tunnel):** `curl.exe http://127.0.0.1:11435/api/tags`
- **Kylo Docker (on power-1):** `docker ps` should list `kylo-pg`, `kylo-redpanda`, consumers
- **Hub status:** `.\scripts\hub_status.ps1 -Worker power-1`
