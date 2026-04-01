"""Probe which package fields exist and match OrderItem.OriginId."""
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

CREDS = "E:/secrets/gcp/growflowapi.txt"
ORIGIN = "1A40E01000018AD000283231"

# Try fields that might hold the compliance tag
CANDIDATES = [
    "PackageLabel",
    "Label",
    "SourceLabel",
    "InventoryTag",
    "Tag",
    "Barcode",
    "ExternalIdentifier",
    "SourcePackageLabel",
    "GlobalProductId",
    "BatchId",
    "BatchNumber",
    "SourcePackageId",
    "IntegrationId",
    "IntegrationKey",
    "SourceId",
    "InventoryId",
    "MetrcId",
    "ComplianceId",
    "RegulatoryId",
    "UID",
    "SourceReceivedAt",
]

for field in CANDIDATES:
    q = f"""
query {{
  findPackages(first: 1) {{
    edges {{
      node {{
        id
        objectId
        SKU
        {field}
      }}
    }}
  }}
}}
"""
    try:
        r = graphql_request(q, credentials_path=CREDS)
    except RuntimeError as e:
        print(field, "HTTP", str(e)[:160])
        continue
    err = r.get("errors")
    if err:
        print(field, "ERROR", err[0].get("message", err)[:120])
    else:
        node = (r.get("data") or {}).get("findPackages", {}).get("edges", [{}])[0].get("node") or {}
        print(field, "OK", "sample:", {k: node.get(k) for k in ["SKU", field] if k in node})

# Try where filter on PackageLabel / Label
for wf in [
    {"PackageLabel": {"equalTo": ORIGIN}},
    {"Label": {"equalTo": ORIGIN}},
]:
    q = """
query P($where: PackagesWhereInput) {
  findPackages(first: 5, where: $where) {
    edges { node { id objectId SKU createdAt } }
  }
}
"""
    try:
        r = graphql_request(q, variables={"where": wf}, credentials_path=CREDS)
        print("WHERE", list(wf.keys())[0], "->", r.get("errors") or "ok")
    except RuntimeError as e:
        print("WHERE", wf, "HTTP", str(e)[:200])
