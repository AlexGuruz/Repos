# Growflow Data Validation Gateway

## Architecture

Validation flow is now:

`metric request -> approved query template -> raw response persisted -> schema/shape validation -> target alignment validation -> normalization -> sanity checks -> validation report -> trusted output (if allowed by mode)`

Gateway module: `lib/data_validation_gateway.py`

State paths:

- raw responses: `state/raw_responses/{metric_id}/{request_id}.json`
- trusted outputs: `state/trusted_outputs/{metric_id}/{request_id}.json`
- reports: `state/validation_reports/{metric_id}/{request_id}.json`

## Contract Schema

Metric contracts are in `contracts/{metric_id}.json`.

Each contract defines:

- identity/business intent (`metric_id`, `description`, `business_question`)
- allowed query templates (`allowed_query_template_ids`)
- response contract (`expected_root_path`, `required_fields`, `optional_fields`, `field_types`)
- alignment expectations (date, store/org, brand/category expectations)
- policy (`empty_result_policy`, `duplicate_policy`)
- sanity checks (`dedupe_key_fields`, `non_negative_field`)
- allowed consumers and risk/confidence metadata
- **`field_confidence`** — per-path or logical-field tier: `confirmed` | `inferred` | `unstable` (see `docs/GROWFLOW_SCHEMA_CONFIDENCE_PLAN.md`)
- **`confidence_level`** — metric-level intent (e.g. `high` for promoted business metrics)

## Query Template Registry

Registry path: `config/query_templates.yaml` (JSON-compatible YAML list).

Each template binds metric to GraphQL operation/source and expected root. Scripts should use template IDs rather than ad-hoc assumptions.

## Modes

- `strict`
  - fail closed if any hard failure or warning is present
  - no trusted output on failure
  - default for dashboard/prepared-context/AI/par use cases
- `warning`
  - hard failures still block trusted output
  - warnings are allowed with reduced confidence
- `discovery`
  - raw + report only
  - no trusted output written
  - intended for schema discovery metrics

## Field confidence, numeric score, and schema drift

Each validation **report** and **trusted output** includes:

- **`confidence_score`** — float in `[0, 1]` from contract `field_confidence` mix, reduced on schema drift warnings or capped low in `discovery` mode.
- **`confidence`** (report) / **`confidence_label`** (trusted file) — discrete label for UI and logs.
- **`field_confidence`** — copy of the contract’s tier map for audit.
- **`field_confidence_counts`** — count of paths per tier.

**Schema verification** (`lib/schema_verification.py`):

- Baselines live under `state/schema_fingerprints/{metric_id}.json`.
- Report block **`schema_verification`** holds drift details; **`schema_drift_warnings`** lists concise messages.

**Optional request `context` flags** (passed into `validate_and_normalize`):

- `update_schema_baseline: true` — refresh fingerprint baseline when validation succeeds.
- `fail_on_schema_drift: true` — add hard failure `schema_drift_critical` when drift marks critical missing paths.

## Brand / category normalization

After row normalization, the gateway applies `lib/brand_category_normalize.apply_to_rows` using `config/brand_category_normalization.json` for canonical brand/category columns on supported metrics. Unmapped strings remain usable but are treated as **inferred** tier in confidence accounting.

## Script Integration

Integrated scripts:

- `scripts/build_projection_by_category_brand.py` (`projection_by_category_brand`)
- `scripts/build_transfer_receipts_db.py` (`transfer_receipts`)
- `scripts/export_transfer_receipt_units.py` (`transfer_units`)
- `scripts/rank_mj_brands_profit_velocity_sheet.py` (`brand_profit_velocity`)

Pattern per script:

1. set `metric_id` + `template_id`
2. pass raw JSON payload to `validate_and_normalize(...)`
3. read validation report path from result and log it
4. fail/continue per selected mode
5. only treat output as trusted when gateway result is `ok`

## Validation Report Interpretation

Report payload includes:

- root path detection (`expected_root_found`)
- schema/shape failures (`missing_required_fields`, `type_errors`)
- policy outcomes (`empty_result_status`, `duplicate_count`)
- alignment and parser warnings
- confidence label, **`confidence_score`**, **`field_confidence_counts`**, **`schema_verification`**, **`schema_drift_warnings`**
- hard-failure list
- artifact paths for raw/trusted/report

Common failure categories surfaced explicitly:

- wrong root path
- missing fields
- wrong types
- empty results (if disallowed)
- date misalignment
- parse/schema drift signals

## Command Center Status Display

Command Center endpoint is added in ai-lab backend:

- `GET /api/growflow/validation-status`

It reads latest validation reports by metric and returns status blocks for UI color coding (green/yellow/red behavior can be based on `ok` and warning/error presence). Response rows include **`confidence_score`**, **`field_confidence_counts`**, and a compact **`schema_drift`** summary when present.

Prepared context `growflow_snapshot` embeds the same fields under `data.validation_status_by_metric` for AI consumption.

## Promotion Checklist for New Metrics

1. add contract file in `contracts/`
2. add template entry in `config/query_templates.yaml`
3. add matrix row + detail section in `docs/GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md`
4. integrate canonical script call to gateway with metric/template IDs
5. add tests for happy path + root/field/type/empty/duplicate/date/mode cases
6. confirm prepared context and command center read the new metric status
7. document **`field_confidence`** for every required/optional API path and align the matrix inventory
8. add or extend `tests/test_schema_verification.py` when fingerprint rules change

Full confidence architecture: **`docs/GROWFLOW_SCHEMA_CONFIDENCE_PLAN.md`**
