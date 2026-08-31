# SaaS phase (deferred)

Do **not** start IdP, multi-tenant DB, hosted workers, or Postgres cutover until:

1. Phase 0–4 of Growflow Ops Platform are complete
2. Retail/consign/capital SLOs are green for **2+ consecutive weeks** on the internal host

Seams already present for a future cut:

- `org_id` (`config/platform.yaml`, fact-store `schema_meta`, JSON meta)
- `GrowflowPlatformConfig` env/path injection
- `PlatformJob` orchestrator interface
- Read-model contracts under `contracts/`

See [GROWFLOW_OPS_PLATFORM.md](GROWFLOW_OPS_PLATFORM.md).
