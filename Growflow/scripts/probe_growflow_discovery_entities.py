"""Try priority schema operations from docs (findProducts, findOrders, …) on live Retail endpoint."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request


def _load_org() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = _root / "config" / "config.yaml"
    if not cfg.is_file():
        return
    t = cfg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^\s*org_id:\s*["\']?([^"\'#\n]+)', t, re.MULTILINE)
    if m:
        os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")


def try_query(name: str, q: str, cp: str) -> None:
    try:
        r = graphql_request(q.strip(), credentials_path=cp)
    except Exception as e:
        print(f"{name}: HTTP/runtime -> {str(e)[:180]}")
        return
    if r.get("errors"):
        print(f"{name}: GraphQL → {r['errors'][0].get('message', r['errors'])[:200]}")
        return
    print(f"{name}: OK keys={(r.get('data') or {}).keys()}")
    print(json.dumps(r.get("data"), indent=2)[:1200])


def main() -> None:
    _load_org()
    cp = os.environ.get("GROWFLOW_CREDENTIALS_PATH") or (
        "E:/secrets/gcp/growflowapi.txt" if Path("E:/secrets/gcp/growflowapi.txt").is_file() else None
    )
    if not cp:
        sys.exit("no creds")

    queries = [
        (
            "findProducts",
            """
query { findProducts(first: 3) {
  edges { node { objectId Name SKU } }
  pageInfo { hasNextPage }
} }""",
        ),
        (
            "findBrands",
            """
query { findBrands(first: 3) {
  edges { node { objectId Name } }
} }""",
        ),
        (
            "findProductCategories",
            """
query { findProductCategories(first: 3) {
  edges { node { objectId Name } }
} }""",
        ),
        (
            "findOrders",
            """
query { findOrders(first: 2) {
  edges { node { objectId id CompletedAt Total } }
} }""",
        ),
        (
            "findStores",
            """
query { findStores(first: 3) {
  edges { node { objectId Name } }
} }""",
        ),
    ]
    for n, q in queries:
        try_query(n, q, cp)
        print()


if __name__ == "__main__":
    main()
