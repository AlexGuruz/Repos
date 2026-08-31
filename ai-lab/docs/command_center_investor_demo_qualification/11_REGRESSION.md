# Stage 12 — Regression + console

## Backend pytest

```powershell
cd E:\Repos\ai-lab\command-center\command-center\backend
$env:PYTHONPATH = "E:\Repos\ai-lab"
..\.venv\Scripts\python.exe -m pytest tests/test_channels.py tests/test_feed_bus.py tests/test_tunnel_scheduler.py `
  tests/test_observability_channels.py tests/test_channel_load_isolation.py `
  tests/test_supervisor_bridge_policy_parity.py tests/test_events_router.py -q
```

**Result:** 28 passed, 4 warnings (~17.6s test time; ~72s wall). Evidence: `evidence/stage12_pytest.txt`

## Frontend

```powershell
cd ...\frontend
npm.cmd test -- --run src/hooks/useWebSocket.test.jsx src/components/ChatPanel.test.jsx
npm.cmd run build
```

**Result:** 10 tests passed (2 files); production build OK (~44s). Evidence: `stage12_frontend_test.txt`, `stage12_frontend_build.txt`

## Live smoke

`scripts/smoke_approvals_e2e.py http://127.0.0.1:8000` → **E2E_OK** (exit 0). Evidence: `evidence/stage12_smoke_approvals.txt`.

Note: smoke created `PAR-7C0BA062` (`_cc_always_smoke`); remove manually if not wanted on disk.

## Clean-start smoke (stop → free ports → full start → one safe approve → worker exec → stop)

**NOT COMPLETED** as a separate bounce after regression (worker already failing; Stages 1–2 already recorded clean start into full mode). Re-bounce omitted to avoid losing remaining log evidence mid-write.

## Stage 12 exit

**PASS** for unit/regression/build. **FAIL** for clean-start smoke completeness + browser console capture depth.
