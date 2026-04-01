import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_graphql import graphql_request

CREDS = "E:/secrets/gcp/growflowapi.txt"
now = datetime.now(timezone.utc)
start = now - timedelta(days=365)
where = {
    "SoldAt": {
        "greaterThanOrEqualTo": start.strftime("%Y-%m-%dT00:00:00.000Z"),
        "lessThanOrEqualTo": now.strftime("%Y-%m-%dT23:59:59.999Z"),
    },
    "Product": {"have": {"Name": {"matchesRegex": "(?i)CARTEL 7PK DIAM INFU PREROLL"}}},
}
q = """
query Oi($first: Int, $where: OrderItemsWhereInput) {
  findOrderItems(first: $first, where: $where) {
    count
    edges { node { id Product { Name } } }
  }
}
"""
r = graphql_request(q, variables={"first": 5, "where": where}, credentials_path=CREDS)
print(r)
