---
status: active
project: meta
type: plan
---

# Active Priorities

Check at session start. Verify real state before acting.

## Open

- [ ] Growflow Ops Platform: run real retail refresh (`run_platform_orchestrator.py --kind full`) until fixture dashboard replaced
- [ ] Operator Desk Gates 4–8 (CC mount, write proposals, smoke)
- [ ] Confirm Gmail `accounts --auth-check` on Acheron before live email digest
- [ ] Reconcile Project-Kylo `global.yaml` vs documented audit freeze (human ops — not Operator Desk)

## Parked

- Voice / STT / TTS
- Kylo read-only status surface
- Growflow refresh-as-approval (requires B3 overturn)
- SaaS multi-tenant (see Growflow/docs/SAAS_PHASE_DEFERRED.md)

## Done

- [x] Accept Operator Desk B1–B3
- [x] Gate 0 baseline + Gate 2 package `operator_desk` (tests green)
- [x] Growflow Ops Platform Phase 0–4 scaffolding (catalog, truthful snapshot, platform status, schedulers, BI report path)
