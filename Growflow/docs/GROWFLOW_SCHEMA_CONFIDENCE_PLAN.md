# Growflow schema confidence plan

This document is the authoritative plan for moving core business metrics from ambiguous or “partial trust” language to **high-confidence, explicitly tiered** schema handling. It ties together contracts, the API schema matrix, the validation gateway, fingerprint baselines, brand/category normalization, downstream prepared context, and Command Center.

## 1. Inventory: inferred / uncertain fields

**Source of truth:** `contracts/*.json` → `field_confidence` (per GraphQL path or logical field), plus the matrix section **Inferred / uncertain inventory** in `docs/GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md`.

| Metric | Where to look | Inferred (summary) | Unstable (summary) |
| --- | --- | --- | --- |
| `sales_today` | `contracts/sales_today.json` | `COG`, `ProductCategory.Name` | `Product.Brand.Name` |
| `sales_by_brand_category` | `contracts/sales_by_brand_category.json` | `COG`, optional `NetPrice` | `Product.Brand.Name` |
| `inventory_on_hand` | `contracts/inventory_on_hand.json` | `OriginalQty`, `Cost` | `Product.Brand.Name` |
| `transfer_receipts` | `contracts/transfer_receipts.json` | `Store.*`, `ReceivingStore.*` | `Packages` |
| `transfer_units` | `contracts/transfer_units.json` | nested `Packages[].Product.objectId` | `Packages`, `Packages[].Product.Brand.Name` |
| `brand_profit_velocity` | `contracts/brand_profit_velocity.json` | `COG`, `ProductCategory.Name` | `Product.Brand.Name` |
| `projection_by_category_brand` | `contracts/projection_by_category_brand.json` | `COG`, `SKU` | `Product.Brand.Name` |
| `schema_discovery` | `contracts/schema_discovery.json` | n/a | entire payload (discovery only) |

**Matrix:** `docs/GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md` — master table **Current Confidence** column uses **high** for trusted metrics; **Status** is **trusted** or **discovery** (no partial-trust row for promoted metrics).

## 2. Field-confidence annotations

Three tiers are enforced in contracts and propagated by the gateway:

| Tier | Definition |
| --- | --- |
| `confirmed` | Field is selected in approved templates, used in canonical scripts, and validated for presence/type at the gateway where required. |
| `inferred` | Field is queried or derived but semantics depend on business rules, optional COG, heuristics, or downstream mapping. |
| `unstable` | Known API variance: nullable relations, nested arrays, partner-doc-only stability, or frequent rename risk. |

**Implementation:** each contract’s `field_confidence` object maps dotted paths (or logical keys) to one of `confirmed` | `inferred` | `unstable`. Metric-level `confidence_level` is set to **high** for promoted business metrics; residual risk is isolated to tiers above.

## 3. Schema verification layer

**Module:** `lib/schema_verification.py`

**Behavior:**

- Flattens normalized sample rows to path fingerprints.
- Compares current run to baseline JSON under `state/schema_fingerprints/{metric_id}.json`.
- Surfaces **missing paths**, **renamed/drift** hints, and optional **critical** missing paths when configured.

**Gateway integration:** `lib/data_validation_gateway.py` calls `verify_against_baseline` during `validate_and_normalize`. Report fields:

- `schema_verification` — full drift block (baseline existence, drift detail).
- `schema_drift_warnings` — list of human-readable warnings for UI and logs.

**Request context flags (callers):**

- `update_schema_baseline: true` — refresh baseline after successful validation (use sparingly, e.g. after intentional schema promotion).
- `fail_on_schema_drift: true` — treat critical missing paths as hard failures (`schema_drift_critical`).

**Tests:** `tests/test_schema_verification.py` — baseline update, drift detection, fingerprint stability.

## 4. Brand / category normalization mapping layer

**Config:** `config/brand_category_normalization.json` — canonical brand names, canonical categories, and explicit string → canonical rules.

**Module:** `lib/brand_category_normalize.py` — applies rules to normalized rows (`canonical_brand`, `canonical_category`, mapping provenance where applicable).

**Contract linkage:** metrics that roll up by brand/category declare `brand_category_expectations` and list unstable/inferred API paths in `field_confidence`. Exact map hits can be treated as **confirmed** mapping tier; unmatched strings remain **inferred** until a rule is added.

## 5. Confidence propagation

**Numeric score:** `confidence_score` in `[0, 1]` on every validation report and on trusted output JSON. Derived from contract `field_confidence` weights, adjusted down for schema drift warnings and for discovery mode.

**Label:** `confidence` on the report is a discrete label (e.g. high / partial / discovery) from `_confidence_label_from_score` for human-readable status.

**Counts:** `field_confidence_counts` summarizes how many paths sit in each tier (auditability).

**Trusted artifact:** `state/trusted_outputs/{metric_id}/{request_id}.json` includes `confidence_score`, `confidence_label`, `field_confidence`, `field_confidence_counts`, `schema_drift`, and `rows`.

**Prepared context:** `ai-lab/brain/prepared_context/builders.py` → `build_growflow_snapshot()` enriches `validation_status_by_metric` with `confidence_score`, `confidence_label`, `field_confidence_counts`, and `schema_drift_summary` from the latest report per metric.

**Command Center:** `GET /api/growflow/validation-status` returns the same fields per metric row for the Tools panel; UI may show label + numeric score.

## 6. Tests for schema drift

| File | Coverage |
| --- | --- |
| `tests/test_schema_verification.py` | Fingerprint shape, baseline write, drift detection, critical missing paths. |
| `tests/test_data_validation_gateway.py` | Gateway integration with metrics, modes, and trusted output gates (extend when adding new metrics). |

## Operational checklist

1. After API or template change: run integrated scripts in **warning** mode first; inspect `schema_drift_warnings`.
2. If drift is expected and validated: run once with `update_schema_baseline: true` (or documented manual baseline update).
3. Expand `brand_category_normalization.json` when new brands/categories appear in production strings.
4. Keep matrix **Inferred / uncertain inventory** in sync when `field_confidence` changes.

## Related documents

- `docs/GROWFLOW_DATA_VALIDATION_GATEWAY.md` — gateway modes, artifacts, and confidence fields.
- `docs/GROWFLOW_API_SCHEMA_RESPONSE_MATRIX.md` — metric ↔ template ↔ field matrix and trust narrative.
