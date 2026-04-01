# Main rig: reaching the worker node

This doc is for the **main rig** (where ai-lab/command-center runs). It covers how to point the main rig at the worker and how to confirm this machine’s local AI can reach the worker.

## 1. How the main rig reaches the worker

Two options:

- **SSH tunnel (recommended)**  
  The main rig runs an SSH tunnel so that `127.0.0.1:8765`, `5678`, and `11434` on the main rig forward to the same ports on the worker. No direct firewall rules on the worker are required for the main rig; everything goes over SSH.

- **Direct to worker IP**  
  The main rig connects to the worker’s IP (e.g. `http://192.168.1.50:8765`). This requires the worker’s firewall to allow inbound TCP on 8765, 5678, 11434 (Private and Public profiles). On the worker, run the firewall script once as Administrator (see worker docs).

## 2. Main rig setup

### 2.1 If you use the SSH tunnel

1. **Start the tunnel first** (before starting the command center or any tool that talks to the worker).  
   Example for worker at **worker-node** with user **zacle**:

   ```bash
   ssh -N -L 8765:127.0.0.1:8765 -L 5678:127.0.0.1:5678 -L 11434:127.0.0.1:11434 zacle@worker-node
   ```

   Or on Windows (PowerShell), from the ai-lab repo (defaults: `zacle@worker-node`):

   ```powershell
   .\scripts\start_worker_tunnel.ps1
   ```

   To override: `.\scripts\start_worker_tunnel.ps1 -User zacle -WorkerHost worker-node`

   Leave this session open while you use the main rig.

   **Recommended (no terminal open):** install a background watchdog using the Scheduled Task installer:

   ```powershell
   .\scripts\setup_worker_tunnel_task.ps1 -User zacle -WorkerHost worker-node
   ```
   After that, the tunnel should survive logoff/reboots and you can start command-center/worker tools normally.

2. **Environment variables (optional).**  
   The registry in `ops/registry/workers.yaml` already sets `base_url` to `http://127.0.0.1:8765` (and 5678, 11434). So if the tunnel is running, you often don’t need to set anything.  
   If you want to override:

   ```bash
   export WORKER_ASSISTANT_URL=http://127.0.0.1:8765
   export WORKER_N8N_URL=http://127.0.0.1:5678
   export OLLAMA_HOST=http://127.0.0.1:11434
   ```

   Windows (cmd):

   ```cmd
   set WORKER_ASSISTANT_URL=http://127.0.0.1:8765
   set WORKER_N8N_URL=http://127.0.0.1:5678
   set OLLAMA_HOST=http://127.0.0.1:11434
   ```

3. **Confirm connectivity** (see section 3).

### 2.2 If you connect directly to the worker IP

1. On the **worker**, run the firewall script once as Administrator so inbound TCP 8765, 5678, 11434 are allowed (Private and Public). See worker docs (e.g. `C:\worker\docs\MAIN_RIG_ORCHESTRATION.md`).

2. On the **main rig**, set URLs to the worker’s host or IP (e.g. **worker-node** or its IP):

   ```bash
   export WORKER_ASSISTANT_URL=http://worker-node:8765
   export WORKER_N8N_URL=http://worker-node:5678
   export OLLAMA_HOST=http://worker-node:11434
   ```

3. **Confirm connectivity** (see section 3).

## 3. Confirm this machine can reach the worker

From the **main rig**, from the ai-lab repo root:

```bash
# From ai-lab repo root; ensure Python can import brain (e.g. set PYTHONPATH)
python scripts/check_worker_connectivity.py
```

Or with explicit path:

```bash
cd E:\Repos\ai-lab
set PYTHONPATH=%CD%
python scripts/check_worker_connectivity.py
```

- If you see **"Worker reachable: yes"** and all three services **ok**, the main rig’s local AI can reach the worker.
- If you see **"Connection refused" (WinError 10061)** or **"Tunnel: down"**:
  - **Using tunnel:** Start the SSH tunnel (section 2.1 step 1) and run the script again.
  - **Using direct IP:** Ensure the worker firewall script was run (Private + Public) and the worker’s network profile matches the rules; retry.

You can also ask in chat: *“Is the worker up?”* or *“Check worker health”* — the assistant uses the same health checks.

## 4. Troubleshooting: connection refused

| Cause | What to do |
|-------|------------|
| **Tunnel not running** (main rig uses localhost) | Start the SSH tunnel (section 2.1). No tunnel ⇒ nothing listening on main’s 127.0.0.1 ⇒ connection refused. |
| **Direct IP + Windows Firewall** | On the **worker**, run the firewall script as Administrator so rules exist for **Public** (and Private). If the worker’s network is Public and only Private rules existed, inbound is still blocked. |
| **Wrong URL or port** | Check env vars or `ops/registry/workers.yaml` base_url. Ports: 8765 (Worker Assistant), 5678 (n8n), 11434 (Ollama). |
| **Worker services not listening** | On the worker, ensure all three services are running and listening on 8765, 5678, 11434. |

## 5. Registry reference

- **Worker and ports:** `ops/registry/workers.yaml` (worker-rig-01, service_definitions with `local_tunnel_port` and `base_url`).
- **URL resolution:** Env vars `WORKER_ASSISTANT_URL`, `WORKER_N8N_URL`, `OLLAMA_HOST` override registry; otherwise `brain.worker_services` uses the registry `base_url`.
