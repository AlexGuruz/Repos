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
- confidence label and hard-failure list
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

It reads latest validation reports by metric and returns status blocks for UI color coding (green/yellow/red behavior can be based on `ok` and warning/error presence).

## Promotion Checklist for New Metrics

1. add contract file in `contracts/`
2. add template entry in `config/query_templates.yaml`
3. add matrix row + detail section in `docs/GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md`
4. integrate canonical script call to gateway with metric/template IDs
5. add tests for happy path + root/field/type/empty/duplicate/date/mode cases
6. confirm prepared context and command center read the new metric status
7. keep confidence/risk notes explicit until schema is validated from trusted source
