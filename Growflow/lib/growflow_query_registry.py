"""
Versioned registry mapping query template IDs to GraphQL query strings.

Bump template suffix (_v2) when field selections change; validation gateway tracks drift.
"""
from __future__ import annotations

import hashlib
from typing import Any

from lib import growflow_queries as gq

REGISTRY: dict[str, dict[str, Any]] = {
    "order_items_sales_today_v1": {
        "operation": "findOrderItems",
        "query": gq.ORDER_ITEMS_QUERY,
        "version": 1,
    },
    "order_items_retail_dashboard_v1": {
        "operation": "findOrderItems",
        "query": gq.ORDER_ITEMS_RETAIL_DASHBOARD_QUERY,
        "version": 1,
    },
    "orders_retail_dashboard_v1": {
        "operation": "findOrders",
        "query": gq.ORDERS_RETAIL_DASHBOARD_QUERY,
        "version": 1,
    },
    "products_catalog_v1": {
        "operation": "findProducts",
        "query": gq.PRODUCTS_CATALOG_QUERY,
        "version": 1,
    },
    "stores_v1": {
        "operation": "findStores",
        "query": gq.STORES_QUERY,
        "version": 1,
    },
    "order_items_pricing_v1": {
        "operation": "findOrderItems",
        "query": gq.ORDER_ITEMS_PRICING_QUERY,
        "version": 1,
    },
}


def query_for_template(template_id: str) -> str:
    entry = REGISTRY.get(template_id)
    if not entry:
        raise KeyError(f"unknown template_id: {template_id}")
    return str(entry["query"])


def query_hash(template_id: str) -> str:
    q = query_for_template(template_id)
    return hashlib.sha256(q.encode("utf-8")).hexdigest()[:16]


def list_templates() -> list[str]:
    return sorted(REGISTRY.keys())
