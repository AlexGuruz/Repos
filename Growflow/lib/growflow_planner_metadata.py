"""
Run-level metadata for the capital buy planner / layer2 CSV.

Production Retail GraphQL often blocks __schema introspection; we do not infer catalog fields
from findProducts/findBrands until validated against an integrations playground or SDL export.
See docs/GROWFLOW_RETAIL_SCHEMA_MAP.md and docs/GROWFLOW_NEXT_DATA_REQUEST.md.
"""
from __future__ import annotations

# Repeated on every layer2 CSV row for downstream tools (Sheets, BI).
GROUPING_LEVEL = "brand_category"
SCHEMA_VALIDATED = "false"
SCHEMA_SOURCE = "fallback_docs_or_code"
# Until findOrderItems exposes line quantity or findProducts validates units, planners count one line = one unit.
UNIT_MODEL_NOTE = (
    "brand/category grain; 1 line treated as 1 unit unless validated otherwise"
)

# Buy-plan: no row receives more COG than implied by this many days of sales at recent daily burn (cash recovery cap).
CASH_CYCLE_DAYS_DEFAULT = 14.0
