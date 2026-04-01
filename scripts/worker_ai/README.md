# Worker AI scripts (main rig = ACHERON)

Scripts for using the worker-assistant from the main rig via SSH tunnel. **Tunnel runs on ACHERON**, target is **work-node** (192.168.40.25).

| Script | Purpose |
|--------|--------|
| **start_tunnel.ps1** | Start SSH tunnel to `worker@192.168.40.25` (port 8765). Use `-Install` to auto-start at logon. |
| **validate_m5_from_main.ps1** | M5 validation: GET /health and POST /retrieve; exit 0 if both succeed. |
| **M5_SIGNOFF.md** | M5 criteria, validation script pointer, and full usage (manual + auto-start). |

## Quick start (on ACHERON)

```powershell
# Start tunnel (leave window open, or use -Install for logon)
& "E:\Repos\scripts\worker_ai\start_tunnel.ps1"

# Then run drift scan
& "E:\Repos\Project-Kylo\scripts\worker_ai\drift_scan.ps1" -BaseUrl "http://127.0.0.1:8765"
```

## Auto-start tunnel after reboot

On ACHERON, run **once**:

```powershell
& "E:\Repos\scripts\worker_ai\start_tunnel.ps1" -Install
```

Use key-based SSH auth for unattended use. To remove: `Unregister-ScheduledTask -TaskName 'WorkerAssistantTunnel'`

See **docs/WORKER_AI_STATUS.md** for rig names, full checklist, and manual tunnel command. See **M5_SIGNOFF.md** for M5 details.
