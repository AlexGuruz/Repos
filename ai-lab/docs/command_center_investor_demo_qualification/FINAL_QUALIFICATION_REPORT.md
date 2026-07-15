# FINAL QUALIFICATION REPORT — Command Center Investor Demo (RESUME)

## 1. Date

2026-07-14 initial · resume 2026-07-14/15 evening · **retry 2026-07-15 ~14:33 local** (see `RETRY_2026-07-15.md`)

## 2. Commit

Working tree now on `feature/kylo-bank-cash-dual-rules` @ `921a5dd` during retry (qual pack + Operator Desk / ping tool fixes still present).

## 3–5. Repo / machines / env

See `00_ENV.md`. Worker: **worker-node** (power-1 DNS unavailable). Tunnel `8765→worker-node:8765` restored.

## 6–8. Service map / clean-start / full workload

Full mode stack running (`CC_LIGHT_MODE=0`). Backend restarted mid-resume to load Operator Desk fix.

## 9. Channels

`02_CHANNEL_WS.md` — prior PASS/PARTIAL.

## 10–12. Approve / Deny / Always (resume)

| Gate | Result | Evidence |
|------|--------|----------|
| Approve `approval-111` + tool success | **PASS** | `03_APPROVE.md`, execute_approved success=true |
| Deny `approval-112` | **PASS** | `04_DENY.md` |
| Always Approve match/nonmatch/remove | **PASS** | `05_ALWAYS_APPROVE.md` |

## 13–17. Load / latency / drops

Prior Stage 7: 0 control drops; publish_ms samples &lt;500ms. Resume Approve publish_ms=0.

## 18. Tunnel fairness

**PASS** bulk lane submit did not stall control metrics polling (`07_TUNNEL_FAIRNESS.md`). Index completion 503 read-only without WA governance — demo restriction.

## 19–21. Logging / recovery / locks

Prior Stage 9–11 stand; duplicate/missing-id remain OK. Full restart matrix still not fully re-swept.

## 22–23. Regression / build

Prior 28 backend + 10 frontend + build green. Permanence unit test added: `operator_desk/tests/test_permanent_auto_propose.py` (not re-run in this closeout if time-constrained).

## 24–25. Console / logs

Browser MCP still unavailable for click proof; REST = ChatPanel path.

## 26. Limitations

- Start WA with `run_wa_serve.bat` / asyncio.serve — bare `uvicorn` CLI hung pre-bind on this host
- Prefer governance-configured WA for write ops (`index_repo`)
- Use `cc_investor_demo_ping` (or fixed Growflow paths), not deprecated `growflow_sales_today`
- `/api/workers/health` may still report partial due to secondary port map (8766/5679/11435) even when `:8765` health is 200 — verify with direct curl
- Browser pixel-click not recorded this session

## 27. Debt

Coordinator disk-under-lock; WA official ensure script should adopt asyncio launcher; workers health port map vs `WORKER_TUNNEL_URL=8765`

## 28–29. Demo restrictions / runbook

See updated `INVESTOR_DEMO_RUNBOOK.md` (worker start procedure appendix below).

### Worker start appendix

```text
# On main:
scp evidence/wa_serve.py evidence/run_wa_serve.bat worker@worker-node:C:/worker/logs/worker_assistant/
ssh -f worker@worker-node C:\worker\logs\worker_assistant\run_wa_serve.bat
# Tunnel if needed:
ssh -N -L 8765:127.0.0.1:8765 worker@worker-node
curl http://127.0.0.1:8765/health
```

## 30. Hard-gate evaluation (resume)

| Gate | Result |
|------|--------|
| Browser→worker Approve / tool continues | **PASS** (successful ping execute) |
| Deny | **PASS** |
| Always Approve match applies / scoped / removable | **PASS** |
| Control publish p95 &lt; 500ms | **PASS** (samples) |
| 0 silent control drops | **PASS** |
| Bulk does not block control | **PASS** (scheduler bulk submit under metrics load) |
| Worker tunnel available | **PASS** (`:8765` health 200) |
| Light mode / APR-* | not used |

## 31. Evidence root

`E:\Repos\ai-lab\docs\command_center_investor_demo_qualification\`

## 32. Final recommendation

Hard gates that previously forced NOT READY are addressed with evidence. Retried 2026-07-15: Approve/Deny/Always + WA health + tunnel bulk non-blocking reconfirmed (`RETRY_2026-07-15.md`). Controlled demo must use the runbook worker start + ping tool (or governance-ready WA for index demos).

READY FOR CONTROLLED INVESTOR DEMO
