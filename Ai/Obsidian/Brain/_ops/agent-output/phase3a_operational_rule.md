# Phase 3A Operational Rule

**Created:** 2026-02-03

## Supervisor Restart Procedure

**Any time supervisor.ps1 changes, follow this procedure:**

1. **Stop supervisor cleanly:**
   ```powershell
   C:\worker\ops\oldrig\supervisor-stop.ps1
   ```

2. **Wait 10-20 seconds:**
   ```powershell
   Start-Sleep -Seconds 15
   ```

3. **Start supervisor:**
   ```powershell
   C:\worker\ops\oldrig\supervisor-start.ps1
   ```

4. **Verify status:**
   ```powershell
   C:\worker\ops\oldrig\supervisor-status.ps1
   ```

## Why This Rule Exists

This procedure prevents "old process running old code" from causing silent drift. By stopping the supervisor, waiting for processes to fully terminate, then restarting, we ensure:

- Old supervisor processes are fully terminated
- New supervisor code is loaded fresh
- No race conditions between old and new code
- Clean state for all managed jobs

## Verification Steps

After restart, verify:

1. **Daemon is running:**
   - Check heartbeat log updates: `ssh oldrig "powershell -NoProfile -Command \"Get-Item C:\worker\logs\watchers\daemon_heartbeat.log | Select-Object LastWriteTime,Length\""`
   - Check state file exists: `ssh oldrig "powershell -NoProfile -Command \"Get-Content C:\worker\agents\state\daemon_heartbeat.json -ErrorAction SilentlyContinue\""`

2. **Oneshot jobs are running:**
   - Check supervisor log for oneshot completion messages

3. **Watchdog is active:**
   - Check watchdog log for activity

## Related

- [[phase3a_summary|Phase 3A Summary]]
- [[../30_infra/watchers/supervisor|Supervisor Watcher]]
