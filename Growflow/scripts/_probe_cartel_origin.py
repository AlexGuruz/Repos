"""Sample OrderItem.OriginId for Cartel 7pk lines."""
import os, re, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.growflow_queries import ORDER_ITEMS_QUERY, PAGE_SIZE, fetch_paginated

def yaml_scalar(text, key):
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None

p = _root / "config" / "config.yaml"
if p.is_file():
    t = p.read_text(encoding="utf-8", errors="replace")
    os.environ["GROWFLOW_RETAIL_ORG"] = yaml_scalar(t, "org_id") or ""
cp = r"E:/secrets/gcp/growflowapi.txt"

end = datetime.now(timezone.utc)
start = end - timedelta(days=400)
where = {
    "SoldAt": {
        "greaterThanOrEqualTo": start.strftime("%Y-%m-%dT00:00:00.000Z"),
        "lessThanOrEqualTo": end.strftime("%Y-%m-%dT23:59:59.999Z"),
    },
    "Product": {"have": {"Name": {"matchesRegex": r"(?i)cartel.*7[\s-]*pk.*prer"}}},
}
nodes = fetch_paginated("findOrderItems", ORDER_ITEMS_QUERY, {"first": PAGE_SIZE, "where": where}, credentials_path=cp)
print("lines", len(nodes))
for n in nodes[:25]:
    oid = n.get("OriginId")
    pr = (n.get("Product") or {}).get("Name")
    print(repr(oid), "|", pr)
