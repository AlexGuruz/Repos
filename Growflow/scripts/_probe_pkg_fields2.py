import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

CREDS = "E:/secrets/gcp/growflowapi.txt"

FIELDS = [
    "ExternalId",
    "Source",
    "SourceName",
    "SourceProductId",
    "SourceQty",
    "SourceUom",
    "BatchId",
    "SourceReceivedAt",
]

parts = "\n        ".join(FIELDS)
q = f"""
query {{
  findPackages(first: 3) {{
    edges {{
      node {{
        id
        objectId
        SKU
        createdAt
        {parts}
      }}
    }}
  }}
}}
"""
r = graphql_request(q, credentials_path=CREDS)
if r.get("errors"):
    print(r["errors"])
else:
    for e in (r.get("data") or {}).get("findPackages", {}).get("edges") or []:
        n = e.get("node") or {}
        print(n)
