"""
Shared GrowFlow GraphQL query strings and pagination helpers.

Field selection aligns with internal docs:
- company_bi/DESIGN.md — findOrderItems (SoldAt, GrossPrice, …), findPackages
- company_bi/METRICS.md — GrossPrice in cents, revenue = sum(GrossPrice)/100

TODO(schema truth): When GrowFlow provides SDL or validated samples (docs/GROWFLOW_NEXT_DATA_REQUEST.md),
reconcile line quantity, Product identity, and package/cost linkage before extending selections here.
Do not add findProducts/findBrands/findProductCategories fields from guesswork.

findPackages quantity fields (see docs/GROWFLOW_RETAIL_SCHEMA_MAP.md "Package line quantities"):
- OriginalQty: opening size of the package line (not live on-hand).
- CurrentQty: live remaining quantity; use for "inventory on hand" unless the task explicitly needs original intake.
"""
from __future__ import annotations

from typing import Any

from lib.growflow_graphql import graphql_request

PAGE_SIZE = 100

# Order items: full shape used by prepackaged flower + inventory scripts, plus Brand for allocation.
ORDER_ITEMS_QUERY = """
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        Package { objectId }
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
          Brand { Name }
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""

# Same as ORDER_ITEMS_QUERY but without Brand (older tokens / schema without Brand on Product).
ORDER_ITEMS_QUERY_NO_BRAND = """
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        Package { objectId }
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""

# Same as ORDER_ITEMS_QUERY but without Package (older Retail schema).
ORDER_ITEMS_QUERY_NO_PACKAGE = """
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
          Brand { Name }
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""

# Same as ORDER_ITEMS_QUERY but without Brand or Package (oldest Retail schemas).
ORDER_ITEMS_QUERY_NO_BRAND_NO_PACKAGE = """
query OrderItems($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        SKU
        OriginId
        ProductCategory { Name }
        Product {
          objectId
          Name
          SKU
          createdAt
        }
        NetWeight
        NetWeightUOM
        UnitWeight
        UnitWeightUOM
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""

# OriginalQty vs CurrentQty: see module docstring and GROWFLOW_RETAIL_SCHEMA_MAP.md.
PACKAGES_TABLE_QUERY = """
query Packages($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        id
        createdAt
        OriginalQty
        CurrentQty
        Cost
        SKU
        Product {
          SKU
          Name
          ProductCategory { Name }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""

# Same as PACKAGES_TABLE_QUERY but with Product.Brand for inventory-by-brand joins.
# findOrders.Items is a union (GraphQL reports "ArrayResult"); use inline fragment on OrderItems.
# Same scalars as findOrderItems edges; useful for ticket-level joins. Volume work should still use
# findOrderItems + SoldAt chunks (orders are not ideal to page comprehensively by date).
FIND_ORDERS_ORDER_ITEMS_SAMPLE = """
query OrdersWithItems($first: Int, $after: String) {
  findOrders(first: $first, after: $after) {
    edges {
      node {
        objectId
        CompletedAt
        Total
        Items {
          ... on OrderItems {
            objectId
            SoldAt
            GrossPrice
            NetPrice
            COG
            SKU
            OriginId
            Package { objectId }
            Product {
              objectId
              Name
              SKU
              Brand { Name }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

# OriginalQty vs CurrentQty: same as PACKAGES_TABLE_QUERY.
PACKAGES_TABLE_QUERY_WITH_BRAND = """
query Packages($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        id
        createdAt
        OriginalQty
        CurrentQty
        Cost
        SKU
        Product {
          SKU
          Name
          ProductCategory { Name }
          Brand { Name }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""


def date_range_to_where(field: str, from_iso: str, to_iso: str) -> dict[str, Any]:
    return {
        field: {
            "greaterThanOrEqualTo": from_iso,
            "lessThanOrEqualTo": to_iso,
        }
    }


# Menu OTD / collected revenue: OriginalPrice, Taxes, Product.SalesPrice (see lib/growflow_line_pricing.py).
ORDER_ITEMS_PRICING_QUERY = """
query OrderItemsPricing($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        Price
        OriginalPrice
        Package { objectId }
        Product {
          objectId
          Name
          SalesPrice
          Brand { Name }
          ProductCategory { Name }
        }
        Taxes { ... on Element { value } }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_order_items_pricing(
    base_variables: dict[str, Any],
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """Paginate findOrderItems with menu OTD and tax fields for revenue reporting."""
    return fetch_paginated(
        "findOrderItems",
        ORDER_ITEMS_PRICING_QUERY,
        base_variables,
        credentials_path=credentials_path,
    )


# Retail dashboard / fact ingest: pricing + Store + Orders union (budtender User).
ORDER_ITEMS_RETAIL_DASHBOARD_QUERY = """
query OrderItemsRetailDashboard($first: Int, $after: String, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, after: $after, where: $where) {
    edges {
      node {
        id
        objectId
        SoldAt
        GrossPrice
        NetPrice
        COG
        Price
        OriginalPrice
        Package { objectId }
        ProductCategory { Name }
        Store { objectId Name }
        Product {
          objectId
          Name
          SKU
          SalesPrice
          Brand { Name }
          ProductCategory { Name }
        }
        Taxes { ... on Element { value } }
        Orders {
          ... on Orders {
            objectId
            CompletedAt
            Total
            Subtotal
            Discounts
            Type
            Status
            PreOrderType
            User { objectId username FullName }
            Store { objectId Name }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
    count
  }
}
"""


def fetch_order_items_retail_dashboard(
    base_variables: dict[str, Any],
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """Paginate findOrderItems with retail dashboard field superset."""
    return fetch_paginated(
        "findOrderItems",
        ORDER_ITEMS_RETAIL_DASHBOARD_QUERY,
        base_variables,
        credentials_path=credentials_path,
    )


ORDERS_RETAIL_DASHBOARD_QUERY = """
query OrdersRetailDashboard($first: Int, $after: String, $where: OrdersWhereInput) {
  findOrders(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        CompletedAt
        Total
        Subtotal
        Discounts
        Type
        Status
        PreOrderType
        User { objectId username FullName }
        Store { objectId Name }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_orders_retail_dashboard(
    base_variables: dict[str, Any],
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    return fetch_paginated(
        "findOrders",
        ORDERS_RETAIL_DASHBOARD_QUERY,
        base_variables,
        credentials_path=credentials_path,
    )


PRODUCTS_CATALOG_QUERY = """
query ProductsCatalog($first: Int, $after: String) {
  findProducts(first: $first, after: $after) {
    edges {
      node {
        objectId
        Name
        SKU
        SalesPrice
        Brand { objectId Name }
        ProductCategory { objectId Name }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_products_catalog(
    base_variables: dict[str, Any] | None = None,
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    return fetch_paginated(
        "findProducts",
        PRODUCTS_CATALOG_QUERY,
        base_variables or {"first": PAGE_SIZE},
        credentials_path=credentials_path,
    )


STORES_QUERY = """
query Stores($first: Int, $after: String) {
  findStores(first: $first, after: $after) {
    edges {
      node {
        objectId
        Name
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def fetch_stores(
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    return fetch_paginated("findStores", STORES_QUERY, {"first": PAGE_SIZE}, credentials_path=credentials_path)


def fetch_order_items(
    base_variables: dict[str, Any],
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Paginate findOrderItems with Brand + Package on the line.

    Falls back through no-Brand, no-Package, then no-Brand/no-Package query shapes if the
    schema rejects those fields.
    """
    queries = (
        ORDER_ITEMS_QUERY,
        ORDER_ITEMS_QUERY_NO_BRAND,
        ORDER_ITEMS_QUERY_NO_PACKAGE,
        ORDER_ITEMS_QUERY_NO_BRAND_NO_PACKAGE,
    )
    last_err: RuntimeError | None = None
    for q in queries:
        try:
            return fetch_paginated(
                "findOrderItems", q, base_variables, credentials_path=credentials_path
            )
        except RuntimeError as e:
            last_err = e
            msg = str(e).lower()
            if "cannot query field" in msg and ("brand" in msg or "package" in msg):
                continue
            raise
    if last_err:
        raise last_err
    return []


def fetch_paginated(
    connection_field: str,
    query: str,
    base_variables: dict[str, Any],
    *,
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """Follow pageInfo.hasNextPage until all nodes are collected."""
    out: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        variables = dict(base_variables)
        if after:
            variables["after"] = after
        elif "after" in variables:
            del variables["after"]
        resp = graphql_request(query, variables, credentials_path=credentials_path)
        errs = resp.get("errors")
        if errs:
            msg = errs[0].get("message", str(errs)) if isinstance(errs, list) else str(errs)
            raise RuntimeError(msg)
        conn = (resp.get("data") or {}).get(connection_field) or {}
        for e in conn.get("edges") or []:
            node = e.get("node")
            if node:
                out.append(node)
        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        after = page.get("endCursor")
        if not after:
            break
    return out
