"""Brute-force field probes on findOrderItems (introspection disabled on Retail)."""
from __future__ import annotations

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


def try_fields(fragment: str, cp: str) -> tuple[bool, str]:
    q = f"""
query {{
  findOrderItems(first: 1) {{
    edges {{
      node {{
        id
        objectId
        {fragment}
      }}
    }}
  }}
}}
"""
    try:
        r = graphql_request(q.strip(), credentials_path=cp)
    except RuntimeError as e:
        return False, str(e)
    if r.get("errors"):
        return False, r["errors"][0].get("message", str(r["errors"]))
    return True, "OK"


def main() -> None:
    _load_org()
    cp = os.environ.get("GROWFLOW_CREDENTIALS_PATH") or (
        "E:/secrets/gcp/growflowapi.txt" if Path("E:/secrets/gcp/growflowapi.txt").is_file() else None
    )

    candidates = [
        # quantity-ish
        "Quantity",
        "Qty",
        "quantity",
        "qty",
        "SoldQuantity",
        "soldQuantity",
        "OrderQuantity",
        "orderQuantity",
        "LineQuantity",
        "lineQuantity",
        "ItemQuantity",
        "itemQuantity",
        "ProductQuantity",
        "productQuantity",
        "NumberOfItems",
        "numberOfItems",
        "Count",
        "UnitCount",
        "unitCount",
        "EachCount",
        "eachCount",
        "Multiplier",
        "multiplier",
        "TimesOrdered",
        "timesOrdered",
        "NumUnits",
        "numUnits",
        "Units",
        "units",
        "Amount",
        "amount",
        "EachAmount",
        "eachAmount",
        "PackageCount",
        "packageCount",
        "PackagesSold",
        "packagesSold",
        # nested
        "Order",
        "Sale",
        "Transaction",
        "ParentOrder",
        "parentOrder",
    ]

    nested = {
        "Order": "Order { objectId id }",
        "Sale": "Sale { objectId id }",
        "Transaction": "Transaction { objectId id }",
        "ParentOrder": "ParentOrder { objectId id }",
        "parentOrder": "parentOrder { objectId id }",
    }

    ok: list[str] = []
    for f in candidates:
        if f in nested:
            frag = nested[f]
        else:
            frag = f
        good, msg = try_fields(frag, cp)
        if good:
            ok.append(f)
            print(f"OK   {f}")
        else:
            if "Cannot query field" in msg:
                print(f"skip {f}")
            else:
                print(f"ERR  {f}: {msg[:160]}")

    print()
    print("Accepted fields:", ok if ok else "(none beyond baseline)")


if __name__ == "__main__":
    main()
