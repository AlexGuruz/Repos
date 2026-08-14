# power-1 handoff brief (for Fable 5)

**Generated:** 2026-08-13 (Acheron ops pass)  
**Audience:** Another model/operator taking the next project on or involving **power-1**  
**Sources:** Live SSH probes + `WORKER_CURRENT.md`, `AGENTS.md`, `REPO_PATH_MIGRATION.md`, `THREE_MACHINE_REPO_ALIGNMENT.md`, `layout.json`, migration scripts  
**Secrets:** Redacted. Do not print key material, `.secrets`, or service-account JSON.

---

## 1. Identity

| Field | Value |
|--------|--------|
| **SSH / docs name** | `power-1` (aliases: `CameraServer`, `cameraserver`) |
| **OS hostname** | `CAMERASERVER` |
| **SSH user** | `gregw` |
| **Role** | **Primary worker rig** (runtime), not the main dev brain |
| **Main rig** | **Acheron** (`zacle`) — source of truth for repos, orchestration, Command Center |
| **Sibling GPU worker** | **worker-node** / docs sometimes call it **oldrig** (`worker@worker-node`, LAN `10.1.30.156`) — GPU/Ollama offload, not Kylo primary |
| **Relationship** | Acheron develops & syncs → power-1 runs Kylo Docker/watchers, worker_assistant, n8n, Blue Iris recording |

power-1 is a **runtime mirror / production host**. Acheron holds canonical source at `E:\Repos\...`. Do not treat power-1 trees as the place to invent long-lived source-of-truth edits unless explicitly operating production.

---

## 2. Hardware (live-verified 2026-08-13)

| Item | Live value |
|------|------------|
| **Chassis / model** | AZW **SER** (mini PC) |
| **CPU** | AMD Ryzen 7 **5825U** with Radeon Graphics |
| **Cores / threads** | **8** cores / **16** logical |
| **Max clock (WMI)** | 2000 MHz (boost higher in practice; WMI reports base) |
| **RAM** | **~28 GB** (systeminfo ~28,595 MB; ~27.92 GiB usable) |
| **GPU** | **AMD Radeon (TM) Graphics** (iGPU only) |
| **NVIDIA** | **None** — `nvidia-smi` not present |
| **OS** | Windows **11 Pro** `10.0.26200` (Build 26200), x64 |
| **BIOS** | AMI SERAL301, 4/8/2025 |
| **Boot observed** | 2026-08-11 ~22:32 (local) |

### Disks / volumes (live)

| Drive | Size | Free | Notes |
|-------|------|------|--------|
| **C:** | ~475 GB | ~313 GB | System + `C:\worker\repos` |
| **E:** | ~13,039 GB (~12.7 TB) | ~12,552 GB | Volume name `USB-HDD` — intended Blue Iris / surveillance store |

Docs describe power-1 as an **iGPU mini PC** — do **not** install or tunnel Ollama here. GPU inference belongs on **worker-node** (and main-rig Ollama on Acheron).

---

## 3. Network

### How Acheron reaches power-1

| Path | Address | SSH alias | Notes |
|------|---------|-----------|--------|
| **LAN (preferred)** | `10.1.30.158` | `power-1` / `CameraServer` | Pinned in `~/.ssh/config`; works when Tailscale is down |
| **Tailscale** | `100.77.230.81` | `power-1-ts` | Needs Tailscale Running on Acheron |

**Identity files (local on Acheron):** `~/.ssh/id_ed25519` for power-1 (do not copy keys into docs/chat).

### Typical service ports on power-1

| Port | Service | Acheron tunnel (typical) |
|------|---------|---------------------------|
| **8765** | worker_assistant | Local `:8765` |
| **5678** | n8n | Local `:5678` |
| **5433 / 5434** | Kylo Postgres (Docker) | Usually stay remote / compose network |
| **81** | Blue Iris UI3 (when configured) | Optional |
| **11434** | Ollama | **Not on power-1** — use worker-node `:11435` tunnel or Acheron local |

### Sibling machine (for contrast)

| Machine | LAN | Tailscale | SSH |
|---------|-----|-----------|-----|
| worker-node | `10.1.30.156` | `100.99.177.106` | `worker@worker-node` / `worker-node-ts` |
| Acheron | — | `100.71.161.10` | main rig |

**Barrier KVM:** Acheron ↔ worker-node (display name `work-node`); power-1 is the camera/Kylo box, not the KVM peer.

---

## 4. Filesystem layout (canonical after 2026-08-13 path migration)

### Expected (layout.json / AGENTS.md)

| Role | Path |
|------|------|
| Repos mirror root | `C:\worker\repos` |
| **Kylo mirror** | `C:\worker\repos\products\project-kylo` |
| **Greg mirror** | `C:\worker\repos\products\greg-kylo` |
| **Compatibility alias** | `C:\Project-Kylo` → junction → `C:\worker\repos\products\project-kylo` |
| Gigatt Kylo tree | `C:\Project-Kylo-Gigatt` (migrated from worker-node; separate) |
| Governance / ai-lab copy | `C:\Users\gregw\ai-lab` (`AI_LAB_GOVERNANCE_ROOT`) |
| Secrets | Prefer approved mounts / product `.secrets` — **never** commit; Acheron uses `E:\secrets` for some secrets |

### Live state after this ops pass

| Check | Result |
|-------|--------|
| `C:\worker\repos\products\project-kylo` | **Present** (moved from flat `Project-Kylo`) |
| `C:\worker\repos\products\greg-kylo` | **Present** (moved from flat `Greg-Kylo`) |
| `C:\Project-Kylo` | **Junction** → `C:\worker\repos\products\project-kylo` |
| Compat `C:\worker\repos\Project-Kylo` | **Junction** → same products path (helps stale scripts) |

### Acheron source (do not confuse)

| Product | Acheron path |
|---------|----------------|
| Project Kylo | `E:\Repos\products\project-kylo` |
| Greg Kylo | `E:\Repos\products\greg-kylo` |
| AI Lab | `E:\Repos\products\ai-lab` |

**Retired on Acheron:** `E:\Repos\Project-Kylo` (flat). That path must not be recreated. The **only** intentional `Project-Kylo` alias is **`C:\Project-Kylo` on power-1**.

### Git shape caveat (important)

- On power-1, **Kylo has no nested `.git`** under `products\project-kylo` — it lives inside the **`C:\worker\repos` monorepo**.
- **Greg** has its **own `.git`** under `products\greg-kylo`.
- On Acheron, Kylo is a **nested_git** product (`AlexGuruz/Project-Kylo`). Power-1 mirror topology is **not** identical to Acheron nested-clone layout yet.

---

## 5. Services / stacks typically run here

From `WORKER_CURRENT.md` + registry (authoritative intent):

| Stack | Port / notes | Boot / ops |
|-------|----------------|------------|
| **worker_assistant** | `:8765` | Task `AiLabWorkerAssistant` + supervisor |
| **n8n** | `:5678` | supervisor `n8n_daemon` |
| **Kylo Docker** | PG `:5433`/`:5434`/`:5436`, Redpanda, Redis, UI ports per compose | `kylo-watcher-2026`, `gigatt-kylo-watcher` — **Docker only** (host watcher retired) |
| **Supervisor** | — | `AiLabWorkerSupervisor` at logon |
| **Blue Iris** | UI3 `:81`, record to large disk | Surveillance server role; TV walls on worker-node |
| **Ollama** | — | **Do not run on power-1** |

Env markers often used: `AI_LAB_MACHINE=worker`, `AI_LAB_ENFORCEMENT=1`, `AI_LAB_GOVERNANCE_ROOT=C:\Users\gregw\ai-lab`.

### Live service snapshot (2026-08-13 smoke)

| Check | Result |
|-------|--------|
| Ports 5433, 5434, 8765, 5678, 81 | **Closed** at probe time |
| Docker Desktop / `kylo-watcher-2026` | **Unavailable** (daemon not running) |
| KYLO_2026 heartbeat | **Stale** (~39h at smoke time) |

Interpretation: **path/junction migration succeeded**; **production watchers/assistant were not running** during this pass. Do **not** restart production stacks unless the next task explicitly requires it.

---

## 6. Do / don’t

### Do

- Treat **Acheron** `E:\Repos\products\...` as source for code changes.
- Use **`C:\Project-Kylo`** or **`C:\worker\repos\products\project-kylo`** on power-1 for runtime.
- Prefer existing scripts: `tools\migration\power1_junction.ps1`, `power1_smoke.ps1`, `products\ai-lab\scripts\_power1_*.ps1`, `sync_kylo_code_acheron_to_workers.ps1`.
- SSH with `ssh power-1 "..."` (LAN) before falling back to `power-1-ts`.
- Run **smoke** after path/sync changes; record WARN vs FAIL separately.
- Keep Blue Iris recording on power-1; keep heavy GPU/decode on worker-node.

### Don’t

- Don’t assume flat **`E:\Repos\Project-Kylo`** exists anywhere as a live path.
- Don’t assume power-1 still uses only `C:\worker\repos\Project-Kylo` as a **real directory** — after 2026-08-13 it is a **compat junction**.
- Don’t **git push from the worker** unless the human explicitly orders it.
- Don’t change **global git config** casually; use `git -c safe.directory=...` when needed.
- Don’t **tar-sync / reset --hard** over dirty worker trees blindly — status first.
- Don’t install **Ollama** on power-1.
- Don’t restart Kylo watchers / Docker / supervisor “for curiosity” after path work.
- Don’t put secrets in chat, commits, or the handoff brief.

---

## 7. Access patterns (redacted)

```powershell
# Connectivity
ssh power-1 "echo ok"
ssh power-1-ts "echo ok"   # Tailscale

# Identity / paths
ssh power-1 "echo %COMPUTERNAME%"
# Prefer scp + remote .ps1 files over nested PowerShell quoting from Acheron

# Migration tooling (from Acheron)
scp E:\Repos\tools\migration\power1_smoke.ps1 power-1:C:/Users/gregw/_power1_smoke.ps1
scp E:\Repos\tools\migration\layout.json power-1:C:/Users/gregw/layout.json
ssh power-1 "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\gregw\_power1_smoke.ps1"

# Kylo code sync Acheron → power-1 (OVERWRITES code files; excludes .git/.kylo/.secrets)
# cd E:\Repos\products\ai-lab
# .\scripts\sync_kylo_code_acheron_to_workers.ps1
# (Skipped on 2026-08-13 because power-1 Kylo had local modifications — see §8)

# Tunnels (from Acheron) — example shape; confirm worker_tunnels.local.json
# ssh -L 8765:localhost:8765 -L 5678:localhost:5678 power-1 -N
```

Useful docs:

- `E:\Repos\products\ai-lab\docs_source\WORKER_CURRENT.md` — single source of worker identity  
- `E:\Repos\docs\REPO_PATH_MIGRATION.md` / `AGENTS.md` — path contract  
- `E:\Repos\docs\THREE_MACHINE_REPO_ALIGNMENT.md` — three-machine audit (may be stale on HEADs)  
- `E:\Repos\tools\migration\layout.json` → `power1` section  

---

## 8. Ops log — what this session did (A)

### Succeeded

1. **SSH** to `power-1` → `CAMERASERVER` / `gregw`.
2. **Hardware probe** (CPU/RAM/GPU/disks/OS) — recorded above.
3. **Path migration (content-preserving move, not tar wipe):**
   - Created `C:\worker\repos\products`
   - Moved `Project-Kylo` → `products\project-kylo`
   - Moved `Greg-Kylo` → `products\greg-kylo`
   - Recreated `C:\Project-Kylo` → `products\project-kylo`
   - Added compat junction `C:\worker\repos\Project-Kylo` → products path
4. **Smoke (paths):** PASS — junction, target, greg root, correct junction target.
5. Confirmed live dirty Kylo files **preserved** across the move.

### Skipped / failed / WARN

| Item | Why |
|------|-----|
| **`sync_kylo_code_acheron_to_workers.ps1`** | **Skipped** — no dry-run; tar extract would overwrite worker-modified files (`config/global.yaml`, instance yaml, audit/poster modules, etc.) |
| **Official `power1_junction.ps1` dry-run via SCP** | Parser error on remote copy (quote/encoding); **junction already applied correctly** by migrate script |
| **Docker / ports / heartbeat** | WARN only — services down/stale; **no restart** performed |
| **Git push / git config** | Not done (by design) |

### Exact command patterns used

```text
ssh -o BatchMode=yes power-1 "echo CONNECT_OK & echo %COMPUTERNAME%"
scp ... power-1:C:/Users/gregw/_remote_power1_*.ps1
ssh ... -File C:\Users\gregw\_remote_power1_status.ps1
ssh ... -File C:\Users\gregw\_remote_power1_hw.ps1
ssh ... -File C:\Users\gregw\_remote_power1_migrate_products.ps1
ssh ... -File C:\Users\gregw\_power1_smoke.ps1
ssh ... -File C:\Users\gregw\_remote_power1_gitcheck.ps1
```

---

## 9. Unknowns / still unverified

- Whether Docker Desktop / Kylo compose / worker_assistant / n8n come back cleanly after next boot without remount fixes.
- Whether any scheduled tasks or compose files still hardcode **flat** `C:\worker\repos\Project-Kylo` as a non-junction path (compat junction should help; not exhaustively audited).
- Full Blue Iris install/config state (runbook exists; ports closed at probe).
- Exact Tailscale status on power-1 during probe (LAN SSH used).
- Monorepo vs nested-git **alignment** for Kylo (Acheron nested clone vs power-1 monorepo subfolder) — needs an explicit future sync strategy.
- `workers.yaml` still lists Ollama on power-1 profile; **`WORKER_CURRENT.md` overrides** — trust WORKER_CURRENT for Ollama placement.
- `WORKER_CURRENT.md` line for Kylo root may still say junction → `repos\Project-Kylo` (pre-products); **runtime now targets `products\project-kylo`**.

---

## 10. One-paragraph briefing for the next model

**power-1** (`CAMERASERVER`, SSH `gregw@power-1` / LAN `10.1.30.158`) is the primary Windows **worker** mini PC (Ryzen 7 5825U, 8c/16t, ~28 GB RAM, AMD iGPU only, C: ~475 GB + E: ~13 TB USB-HDD). It runs Kylo Docker/watchers, worker_assistant `:8765`, n8n `:5678`, and Blue Iris recording — **not** Ollama (that’s worker-node / Acheron). Canonical Kylo runtime path is `C:\worker\repos\products\project-kylo` with alias junction `C:\Project-Kylo`; Greg is `C:\worker\repos\products\greg-kylo`. Acheron source is `E:\Repos\products\...`. As of 2026-08-13 paths/junctions were migrated and smoke-passed, but production services were down and Acheron→worker **code tar-sync was not run** to avoid clobbering local Kylo edits.
