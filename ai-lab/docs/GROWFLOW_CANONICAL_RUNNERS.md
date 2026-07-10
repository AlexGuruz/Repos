# Growflow Canonical Runners (Phase 3)

## 1. Purpose of this phase

Phase 3 does **not** add new automation or wire every script into the agent. It turns the Growflow tree from an unlabeled pile of entrypoints into a **controlled, classified inventory**: what is canonical, what is diagnostic, what is unsafe to register as a tool without approval metadata, and what feeds prepared context. Human owners can review one JSON file and one doc, then decide integration order.

**Machine-readable map:** `ai-lab/state/integration_inventory/growflow_runners.json` (regenerate with `python scripts/generate_growflow_runners_json.py` from the `ai-lab` directory).

**Classifier source:** `ai-lab/brain/integration_inventory/growflow_classify.py` (heuristics + explicit overrides).

## 2. Classification rules

Each discovered `*.py` under the scanned roots gets exactly one **category** label:

| Category | Meaning |
|----------|---------|
| `canonical_runner` | Primary repeatable pipeline or export not tied to a fixed schedule in our map. |
| `scheduled_job_candidate` | Same quality bar as canonical, plus a **recommended recurring cadence** (daily / few days / weekly). |
| `read_safe_tool_candidate` | Read-biased helpers; confirm side effects before any tool registration. |
| `manual_diagnostic` | Probes, scans, one-off analysis, underscore-prefixed ad-hoc scripts. |
| `deprecated_archive_later` | Legacy patches / one-offs; do not treat as production path (do not delete yet). |
| `unsafe_without_approval_metadata` | Writes external state (DB, Sheets, APIs); **must not** be registered as a tool until full approval metadata exists. |
| `unknown_needs_review` | Reserved default in the classifier; the committed `growflow_runners.json` should keep **count 0** — anything landing here should be reclassified before merge. |

**Secondary flag (not a category):** `prepared_context_source: true` when the script’s outputs are inputs to the ai-lab `growflow_snapshot` builder (`brain/prepared_context/builders.py` — exports, transfer receipts, projection dashboard artifacts).

**Registry flag:** `approval_required_for_tool_registry` is `true` for unsafe categories, known write-heavy basenames, and deprecated helpers we do not want auto-promoted.

## 3. Canonical runners

Scripts classified as `canonical_runner` are the **non-scheduled-map** primary entrypoints (still production-grade). See `counts.canonical_runner` in `growflow_runners.json` and the `scripts` array where `category == "canonical_runner"`. Typical areas: brand/stock allocation, landed-cost / projection completion, supplier pace, cartel portfolio projection, discovery query runner, validation helpers promoted as runners.

## 4. Scheduled job candidates

Rows with `category == "scheduled_job_candidate"` align with `SCHEDULED_JOB_CANONICAL_NAMES` in `growflow_classify.py` (projection build, dashboard sheet build, transfer receipts DB/units, top-15 windows export, layout export, schema introspection, company_bi monthly/payroll/recurring summaries, etc.). **Cadence is documented intent only** — no scheduler was added in Phase 3.

## 5. Prepared-context sources

Any row with `prepared_context_source: true` (see `counts.prepared_context_feeders`) matches `PREPARED_CONTEXT_FEEDER_NAMES`: transfer receipts build/export, top-15 export, projection dashboard sheet build, projection dashboard layout export. These are the main on-disk inputs the ai-lab Growflow snapshot expects alongside `METRICS.md` and validation reports.

## 6. Read-safe tool candidates

Rows with `category == "read_safe_tool_candidate"` (e.g. projection CSV validators, company BI read-only audits). **Still verify** arguments and side effects before registering as tools.

## 7. Manual diagnostics

Probe / scan / check / dump / print patterns, `probe_*.py`, and named diagnostics (e.g. efficiency distribution, worst recovery scan). Not used as canonical runners in automation without an explicit promotion review.

## 8. Deprecated / archive-later scripts

`deprecated_archive_later`: patched legacy files (`_patch_*`, `_sellout_final.py`, etc.). Kept in-repo; excluded from canonical automation paths.

## 9. Scripts requiring approval metadata before tool registration

All rows with `approval_required_for_tool_registry: true`, especially `unsafe_without_approval_metadata` (e.g. `ingest_growflow_to_db.py`, `all_categories_inventory_and_daily_rebuild.py`, sheet writers in `UNSAFE_WITHOUT_METADATA_NAMES`). **Do not register** these in `registry/scripts.json` or `brain/tool_registry.py` until approval fields are complete and gates are satisfied.

**Current registry:** The only Growflow-related registered tool remains `growflow_sales_today` (read-only API path under Greg-Kylo integrations), not the Growflow repo batch scripts.

## 10. Recommended next integration order

1. **Read paths first:** prepared-context snapshot already consumes exports — keep validation gates and freshness checks as-is.  
2. **Stable read tools:** schema introspection / discovery in read-only modes for operator questions.  
3. **Scheduled-map jobs:** projection + transfer receipts chain (already classified); wire only with explicit ops approval.  
4. **Write tools last:** DB ingest, sheet publishers, trip doc builders — only with full approval metadata and no gate weakening.

---

## Historical note

Earlier narrative lists of “official tools” from `Growflow/scripts/README.md` are still valid as **human** documentation; Phase 3 adds the **machine** inventory above so tests and audits can assert policy without rescoping every script by hand in markdown.
