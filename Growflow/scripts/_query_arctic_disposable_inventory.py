"""One-off: sum findPackages CurrentQty for Arctic disposable (name/SKU heuristic)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_queries import PAGE_SIZE, fetch_paginated

CREDS_ENV = "GROWFLOW_CREDENTIALS_PATH"
DEFAULT_CREDS = Path("E:/secrets/gcp/growflowapi.txt")

PACKAGES_Q = """
query P($first: Int, $after: String, $where: PackagesWhereInput) {
  findPackages(first: $first, after: $after, where: $where) {
    edges {
      node {
        objectId
        SKU
        CurrentQty
        Product {
          Name
          SKU
          Brand { Name }
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


def _load_org_from_config() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = _root / "config" / "config.yaml"
    if not cfg.is_file():
        return
    text = cfg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^\s*org_id:\s*["\']?([^"\'#\n]+)', text, re.MULTILINE)
    if m:
        os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")


def _creds_path() -> str | None:
    p = os.environ.get(CREDS_ENV) or os.environ.get("GROWFLOW_CREDENTIALS")
    if p and Path(p).is_file():
        return p
    if DEFAULT_CREDS.is_file():
        return str(DEFAULT_CREDS)
    return None


def is_arctic_disposable(node: dict) -> bool:
    pr = node.get("Product") or {}
    blob = " ".join(
        [
            str(pr.get("Name") or ""),
            str(pr.get("SKU") or ""),
            str(node.get("SKU") or ""),
        ]
    ).lower()
    if "arctic" not in blob:
        return False
    return any(x in blob for x in ("dispos", "disposable", "dispo"))


def main() -> int:
    _load_org_from_config()
    creds = _creds_path()
    if not creds:
        print("No Growflow credentials file found.", file=sys.stderr)
        return 1

    where: dict = {
        "CurrentQty": {"greaterThan": 0},
        "Product": {"have": {"Name": {"matchesRegex": "(?i)arctic"}}},
    }
    try:
        nodes = fetch_paginated(
            "findPackages",
            PACKAGES_Q,
            {"first": PAGE_SIZE, "where": where},
            credentials_path=creds,
        )
    except Exception as e:
        print(f"Server filter failed ({e}); falling back to CurrentQty>0 + client filter.", flush=True)
        try:
            nodes = fetch_paginated(
                "findPackages",
                PACKAGES_Q,
                {"first": PAGE_SIZE, "where": {"CurrentQty": {"greaterThan": 0}}},
                credentials_path=creds,
            )
        except Exception as e2:
            print(f"findPackages failed: {e2}", file=sys.stderr)
            return 1
        nodes = [n for n in nodes if is_arctic_disposable(n)]
    else:
        nodes = [n for n in nodes if is_arctic_disposable(n)]

    by_key: dict[tuple[str, str, str, str], int] = {}
    for n in nodes:
        pr = n.get("Product") or {}
        bd = pr.get("Brand") or {}
        bn = bd.get("Name") if isinstance(bd, dict) else ""
        key = (
            str(bn or ""),
            str(pr.get("Name") or ""),
            str(pr.get("SKU") or ""),
            str(n.get("SKU") or ""),
        )
        by_key[key] = by_key.get(key, 0) + int(n.get("CurrentQty") or 0)

    total = sum(by_key.values())
    print(f"Arctic disposable (heuristic): package rows={len(nodes)}  sum(CurrentQty)={total}")
    for k, q in sorted(by_key.items(), key=lambda x: -x[1]):
        print(f"  {q:6d}  brand={k[0]!r}  product={k[1]!r}  prodSKU={k[2]!r}  pkgSKU={k[3]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
