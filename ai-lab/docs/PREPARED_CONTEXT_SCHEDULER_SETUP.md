# Prepared Context Scheduler Setup (Windows)

This guide wires Prepared Context refreshes into Windows Task Scheduler so chat stays fast without rebuilding context on-demand.

## Prereqs

- `ai-lab` repository exists at `E:/Repos/ai-lab` (or pass custom root to script).
- Python is available in `PATH` (or pass `-PythonExe` explicitly).
- You can run `schtasks`.

## Recommended cadences

- `worker_snapshot`: every 10 minutes
- `system_snapshot`: every 15 minutes
- `repo_pulse`: every 45 minutes
- `project_agenda`: daily
- `personal_ops_snapshot`: daily
- `growflow_snapshot`: every 60 minutes

## Option 1: safe dry-run first

```powershell
powershell -ExecutionPolicy Bypass -File "E:/Repos/ai-lab/scripts/setup_prepared_context_tasks.ps1"
```

This prints the exact `schtasks` commands and does not create tasks.

## Option 2: apply tasks

```powershell
powershell -ExecutionPolicy Bypass -File "E:/Repos/ai-lab/scripts/setup_prepared_context_tasks.ps1" -Apply
```

When `-Apply` is used, the script also triggers an initial `--snapshot all` build so the layer is warm immediately.

Optional overrides:

```powershell
powershell -ExecutionPolicy Bypass -File "E:/Repos/ai-lab/scripts/setup_prepared_context_tasks.ps1" `
  -Apply `
  -AiLabRoot "E:/Repos/ai-lab" `
  -PythonExe "C:/Users/<you>/AppData/Local/Programs/Python/Python312/python.exe"
```

## Verify tasks

```powershell
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext Worker"
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext System"
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext RepoPulse"
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext ProjectAgenda"
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext PersonalOps"
schtasks /Query /FO LIST /TN "AI-Lab PreparedContext Growflow"
```

## Remove tasks

```powershell
powershell -ExecutionPolicy Bypass -File "E:/Repos/ai-lab/scripts/remove_prepared_context_tasks.ps1"
```

## Manual one-off refresh

```powershell
python "E:/Repos/ai-lab/scripts/build_prepared_context.py" --snapshot all
```

or per snapshot:

```powershell
python "E:/Repos/ai-lab/scripts/build_prepared_context.py" --snapshot worker_snapshot
```

## Operational notes

- Prepared context is additive and sits before retrieval/model calls.
- If snapshots are stale or missing, orchestrator falls back to normal retrieval/model path.
- Chat does not block on snapshot rebuild; refreshes are background/scheduled.
- Keep approval gates unchanged; these tasks only refresh cached context files.
- Command Center backend now also runs an in-process refresher loop with policy intervals; scheduler tasks are an extra durability layer for machine restarts and offline backend windows.

