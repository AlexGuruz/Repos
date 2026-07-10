import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.growflow_graphql import graphql_request

os.environ.setdefault("GROWFLOW_RETAIL_ORG", "nugzdispensary")
C = "E:/secrets/gcp/growflowapi.txt"
q = """
query {
  findPackages(first: 1, where: { objectId: { equalTo: "J89f0MusuY" } }) {
    edges {
      node {
        id
        objectId
        SKU
        createdAt
      }
    }
  }
}
"""
r = graphql_request(q, credentials_path=C)
print(r)
