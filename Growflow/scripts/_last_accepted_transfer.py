"""Print most recent Accepted transfer (findTransfers order ReceivedAt_DESC)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

QUERY = """
query LastAccepted($first: Int!) {
  findTransfers(first: $first, order: [ReceivedAt_DESC], where: { Status: { equalTo: "Accepted" } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        createdAt
        updatedAt
        Packages {
          ... on Packages {
            objectId
            SKU
            OriginalQty
            CurrentQty
            Cost
            Product {
              Name
              SKU
            }
          }
        }
      }
    }
  }
}
"""


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


def main() -> None:
    _load_org()
    cp = os.environ.get("GROWFLOW_CREDENTIALS_PATH") or (
        "E:/secrets/gcp/growflowapi.txt" if Path("E:/secrets/gcp/growflowapi.txt").is_file() else None
    )
    if not cp and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print("No credentials", file=sys.stderr)
        sys.exit(1)
    r = graphql_request(QUERY, {"first": 1}, credentials_path=cp)
    if r.get("errors"):
        print(json.dumps(r, indent=2))
        sys.exit(1)
    edges = ((r.get("data") or {}).get("findTransfers") or {}).get("edges") or []
    if not edges:
        print("No Accepted transfers found.")
        sys.exit(0)
    print(json.dumps(edges[0].get("node"), indent=2))


if __name__ == "__main__":
    main()
