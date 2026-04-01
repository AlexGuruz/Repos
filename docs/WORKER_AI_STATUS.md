# Worker AI – status and tunnel

## Rig names

| Rig | Machine | Role |
|-----|---------|------|
| **Main** | **ACHERON** | Primary dev machine. You open the SSH tunnel here and run the drift scan. |
| **Worker** | **work-node** (worker-node.lan) | Runs Ollama and worker_assistant. Needs API on 8765 and SSH so ACHERON can connect. |

- Worker LAN IP: **192.168.40.25** (use this if `worker-node` / `worker-node.lan` does not resolve.)
- SSH user on worker: **worker** (e.g. `worker@192.168.40.25`).

---

## Plan status (M1–M6A)

| Milestone | What it is | Status |
|-----------|-------------|--------|
| M1 | Ollama on worker, LAN bind, API | Done |
| M2 | FastAPI worker_assistant | Done |
| M3 | Chroma, /index_repo, /retrieve | Done |
| M4A | Supervisor keeps API running (daemon job on worker) | Done |
| M4B | Scheduled indexing job | Done |
| M5 | Main rig can call worker via tunnel | Pending: tunnel must be opened from ACHERON |
| M6A | Drift scan (main vs worker git) | Implemented; run on ACHERON once tunnel is up |

Implementation is in place through M6A. What’s left is using the tunnel (and drift scan) from the right machine.

---

## SSH tunnel (correct direction)

The tunnel is started **on the main rig** and connects **to the worker**.

- **On ACHERON (main):** run the tunnel and leave that window open (or use the script below).
- **On work-node (worker):** you do **not** run the tunnel. You only need the SSH server and worker_assistant listening on 8765.

### Command (run on ACHERON)

```powershell
ssh -L 8765:localhost:8765 worker@192.168.40.25 -N
```

If host key prompts or `known_hosts` cause issues:

```powershell
ssh -L 8765:localhost:8765 worker@192.168.40.25 -N -o UserKnownHostsFile=NUL -o StrictHostKeyChecking=no
```

By hostname (if DNS/hosts resolve):

```powershell
ssh -L 8765:localhost:8765 worker@worker-node.lan -N
```

### Script (run on ACHERON)

```powershell
& "E:\Repos\scripts\worker_ai\start_tunnel.ps1"
```

Use **key-based SSH** on ACHERON so the tunnel can start without a password (e.g. for scheduled task or after reboot).

---

## Checklist

**On work-node (worker):**

- [ ] SSH server running so ACHERON can connect.
- [ ] worker_assistant running on port 8765 (with `GET /repo_status`, `GET /health`, `POST /retrieve`).
- [ ] Firewall allows SSH from ACHERON if applicable.

**On ACHERON (main):**

1. [ ] Start the tunnel (command or script above); leave the window open or run as scheduled task.
2. [ ] Run drift scan:
   ```powershell
   & "E:\Repos\Project-Kylo\scripts\worker_ai\drift_scan.ps1" -BaseUrl "http://127.0.0.1:8765"
   ```
   (Adjust path if Project-Kylo lives elsewhere on ACHERON.)

If you get 404 for `/repo_status`, the process on work-node serving 8765 is likely an old build — restart worker_assistant on work-node from the repo that has the `repo_status` route.

---

## Note on other scripts

- **setup_ssh_tunnel.ps1** (if present elsewhere) is for a **different** (e.g. reverse) tunnel, not this 8765 forward tunnel. Use the command or `scripts\worker_ai\start_tunnel.ps1` for the main→worker 8765 tunnel.
