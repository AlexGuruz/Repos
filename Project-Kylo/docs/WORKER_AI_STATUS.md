# Worker AI Lab — Status

## Rig names

| Rig | Machine | SSH user | Role |
|-----|---------|----------|------|
| **Main** | ACHERON | zacle | Primary dev machine. Open tunnel here and run drift scan. |
| **Worker** | worker-node (work-node) | worker | Runs Ollama + worker_assistant. Exposes API and SSH for ACHERON. |

Worker LAN IP: `192.168.40.25` (hostname: `worker-node.lan` or `worker-node` if DNS resolves).

---

## Plan status (M1–M6A)

| Milestone | What it is | Status |
|-----------|------------|--------|
| M1 | Ollama on worker, LAN bind, API | Done |
| M2 | FastAPI worker_assistant | Done |
| M3 | Chroma, /index_repo, /retrieve | Done |
| M4A | Supervisor keeps API running | Done (daemon job on worker) |
| M4B | Scheduled indexing job | Done |
| M5 | Main rig can call worker via tunnel | Pending: tunnel must be opened from ACHERON |
| M6A | Drift scan (main vs worker git) | Implemented; run on ACHERON once tunnel is up |

Implementation is in place through M6A. Remaining step: use the tunnel (and drift scan) from the main rig.

---

## One script (main rig)

**On ACHERON (main):** run this. It starts the tunnel if needed (you’ll get an SSH window for password if required), then runs the drift scan:

```powershell
& "E:\Repos\Project-Kylo\scripts\worker_ai\run_drift_scan.ps1"
```

The tunnel uses `127.0.0.1` on the worker side (IPv4) so the connection works. Tunnel is left running for reuse.

---

## SSH tunnel (manual)

The tunnel is **started on the main rig** and connects **to the worker**. Use `127.0.0.1` (not `localhost`) on the remote side for IPv4.

**On ACHERON (main):** run and leave the window open (or use `run_drift_scan.ps1` above):

```powershell
ssh -L 8765:127.0.0.1:8765 worker@192.168.40.25 -N
```

Optional: start tunnel in background only: `& "E:\Repos\Project-Kylo\scripts\worker_ai\start_tunnel.ps1"`

**On worker-node:** do **not** run the tunnel. You only need:

- SSH server (so ACHERON can connect)
- worker_assistant listening on port 8765 (with `GET /repo_status` and other routes)

---

## Checklist

**On worker-node (worker rig):**

- [ ] worker_assistant is running on port 8765 (latest code with `GET /repo_status`)
- [ ] Firewall allows SSH from ACHERON (and optionally port 8765 if you ever need direct LAN access)
- [ ] No tunnel command here

**On ACHERON (main rig):**

- [ ] Run: `& "E:\Repos\Project-Kylo\scripts\worker_ai\run_drift_scan.ps1"` (starts tunnel if needed, then drift scan). Or start the tunnel manually and run `drift_scan.ps1` in a second window.

If you get 404 for `/repo_status`, the process on worker-node serving 8765 is an old build — restart worker_assistant on the worker from the repo that has the `repo_status` route.

---

## Note on other tunnel scripts

`setup_ssh_tunnel.ps1` (if present elsewhere) is for a **different (reverse)** tunnel, not this 8765 forward tunnel. Use the command or `scripts/worker_ai/start_tunnel.ps1` as above.
