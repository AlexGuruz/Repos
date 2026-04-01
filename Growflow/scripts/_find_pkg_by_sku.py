import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

CREDS = "E:/secrets/gcp/growflowapi.txt"
SKU = "18AD000283231"

q = """
query P($where: PackagesWhereInput) {
  findPackages(first: 5, where: $where) {
    edges { node { id objectId SKU createdAt Product { Name } } }
  }
}
"""
r = graphql_request(q, variables={"where": {"SKU": {"equalTo": SKU}}}, credentials_path=CREDS)
print(r)
