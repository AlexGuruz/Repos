# GrowFlow discovery queries (validation harness)

Minimal GraphQL operations to run when you have **integrations playground** access, an **introspection-enabled** URL, or SDL-confirmed field names. They are **not** guaranteed to succeed against production Retail until GrowFlow confirms shapes.

## How to run

From repo root (with credentials and optional URL override):

```bash
set PYTHONPATH=.
python scripts/run_growflow_discovery_queries.py
# Optional: integrations
set GROWFLOW_GRAPHQL_URL=https://retail.growflow.com/c/integrations/graphql
python scripts/run_growflow_discovery_queries.py --credentials E:/secrets/gcp/growflowapi.txt
```

- **OK:** HTTP 200 and no `errors` in the JSON body → selections are plausible for that endpoint.
- **GraphQL errors:** Edit the matching `.graphql` file using the playground schema or SDL — **do not** copy unverified fields into `lib/growflow_queries.py`.

## Extending

Add another `discover_<name>.graphql` file in this folder; `scripts/run_growflow_discovery_queries.py` picks up all `discover_*.graphql` files in sort order. Keep operations minimal until SDL or playground confirms field names.

## Files

| File | Intent |
|------|--------|
| `discover_findOrderItems.graphql` | Smoke test for implemented root (minimal node fields). |
| `discover_findPackages.graphql` | Smoke test for implemented root (minimal node fields). |
| `discover_findProducts.graphql` | Priority: catalog / SKU path (confirm before planner SKU work). |
| `discover_findBrands.graphql` | Brand list vs `Product.Brand` strings. |
| `discover_findProductCategories.graphql` | Category truth vs inferred buckets. |
| `discover_findTransfers.graphql` | Internal movement (expand `node` when schema known). |
| `discover_findTransactions.graphql` | Tender / payment reconciliation (expand when known). |
| `discover_findStores.graphql` | Multi-store filters. |

See also: `docs/GROWFLOW_API.md`, `docs/GROWFLOW_NEXT_DATA_REQUEST.md`, `docs/GROWFLOW_RETAIL_SCHEMA_MAP.md`.
