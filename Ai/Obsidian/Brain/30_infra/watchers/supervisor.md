---
type: supervisor
runs_on: [[30_infra/hosts/oldrig]]
tasks: [Worker-Agents, Worker-Watchdog]
heartbeat: C:\worker\logs\watchers\supervisor_heartbeat.txt
logs:
  - C:\worker\logs\watchers\supervisor.log
  - C:\worker\logs\watchers\watchdog.log
configs: C:\worker\agents\configs\
status: active
created: 2026-02-03
updated: 2026-02-03
---

# Supervisor Watcher

## Overview
Monitors the supervisor system on oldrig, including Worker-Agents and Worker-Watchdog scheduled tasks.

## Target
- **Host**: [[30_infra/hosts/oldrig|oldrig]]
- **Type**: supervisor
- **Tasks**: 
  - Worker-Agents
  - Worker-Watchdog

## Files and Paths

### Heartbeat
- **Path**: `C:\worker\logs\watchers\supervisor_heartbeat.txt`
- **Purpose**: Heartbeat file indicating supervisor is alive
- **Check**: Last write time indicates last activity

### Logs
- **Supervisor Log**: `C:\worker\logs\watchers\supervisor.log`
- **Watchdog Log**: `C:\worker\logs\watchers\watchdog.log`

### Configuration
- **Configs Directory**: `C:\worker\agents\configs\`

### Control Files
- **STOP File**: `C:\worker\agents\STOP`
  - Presence of this file signals supervisor to stop
  - Created by `supervisor-stop.ps1`
  - Removed by `supervisor-start.ps1`

## Operations

### Check Status
```powershell
C:\worker\ops\oldrig\supervisor-status.ps1
```
- Queries scheduled tasks status
- Checks heartbeat file
- Tails last 50 lines of logs
- Saves status to: `C:\worker\logs\supervisor_status_<timestamp>.log`
- Updates vault snapshot: `E:\Ai\Obsidian\Brain\_ops\telemetry\supervisor_status.md`

### Stop Supervisor
```powershell
C:\worker\ops\oldrig\supervisor-stop.ps1
```
- Creates STOP file on oldrig
- Ends Worker-Agents scheduled task

### Start Supervisor
```powershell
C:\worker\ops\oldrig\supervisor-start.ps1
```
- Removes STOP file on oldrig
- Runs Worker-Agents scheduled task

## Related
- [[index|Watchers Index]]
- [[../hosts/oldrig|Oldrig]]
- [[../hosts/newrig|Newrig]]
- [[../../_ops/telemetry/supervisor_status|Supervisor Status Snapshot]]
