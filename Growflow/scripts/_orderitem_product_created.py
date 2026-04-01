import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

CREDS = "E:/secrets/gcp/growflowapi.txt"
Q = """
query Oi($first: Int) {
  findOrderItems(first: $first) {
    edges {
      node {
        OriginId
        SoldAt
        Product { Name createdAt objectId }
      }
    }
  }
}
"""
r = graphql_request(Q, variables={"first": 3}, credentials_path=CREDS)
print(r.get("errors") or r.get("data"))
