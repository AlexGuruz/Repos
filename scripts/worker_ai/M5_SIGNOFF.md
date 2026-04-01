# M5 Sign-off: Worker-assistant reachable from main rig

## Criteria

- **GET /health** returns 200 when called from the main rig (via tunnel).
- **POST /retrieve** returns 200 for a fixed query with `top_k: 2` when called from the main rig (via tunnel).
- Validation is performed by the script below; exit code 0 = M5 complete.

## Validation script

**`scripts/worker_ai/validate_m5_from_main.ps1`**

- Run on the main rig with the tunnel up (and optionally `WORKER_ASSISTANT_URL` set).
- Calls GET `/health` and POST `/retrieve` (fixed query, `top_k: 2`).
- Exits 0 if both succeed, non-zero otherwise; on failure it reminds you to start the tunnel.

---

## How to use from the main rig

### Start the tunnel (manual)

1. **Start tunnel:**  
   `ssh -L 8765:localhost:8765 worker@worker-node -N`  
   Or from the repo:  
   `.\scripts\worker_ai\start_tunnel.ps1`

2. **Optionally set base URL:**  
   `$env:WORKER_ASSISTANT_URL = "http://127.0.0.1:8765"`

3. **From the repo, confirm M5:**  
   `.\scripts\worker_ai\validate_m5_from_main.ps1`

### Auto-start tunnel after reboot (default for other systems)

So the tunnel is running whenever the main rig is logged in, run **once** from the repo (e.g. after clone or on a new machine):

```powershell
.\scripts\worker_ai\start_tunnel.ps1 -Install
```

This registers a scheduled task **WorkerAssistantTunnel** that runs at user logon and starts the SSH tunnel in the background. After reboot, the tunnel will auto-reconnect to `worker@worker-node` on port 8765. Other systems can use this as the default when they need the worker-assistant reachable.

- **Unregister (stop auto-start):**  
  `Unregister-ScheduledTask -TaskName 'WorkerAssistantTunnel'`
- **Custom host/port:**  
  `.\scripts\worker_ai\start_tunnel.ps1 -Install -SshTarget "user@other-host" -LocalPort 8765`

The combined plan’s worker-assistant track (M1–M5) is now fully implemented.
