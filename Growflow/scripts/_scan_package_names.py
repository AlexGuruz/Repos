"""Debug: package Product names containing stix or xtrax (case-insensitive)."""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from lib.growflow_queries import PACKAGES_TABLE_QUERY_WITH_BRAND, PAGE_SIZE, fetch_paginated


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    p = repo / "config" / "config.yaml"
    if p.is_file():
        import re as re2

        m = re2.search(
            r'^\s*org_id:\s*["\']?([^"\'#\n]+)',
            p.read_text(encoding="utf-8", errors="replace"),
            re2.MULTILINE,
        )
        if m:
            os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")
    cp = os.environ.get("GROWFLOW_CREDENTIALS_PATH") or (
        r"E:/secrets/gcp/growflowapi.txt" if Path(r"E:/secrets/gcp/growflowapi.txt").is_file() else None
    )
    pkgs = fetch_paginated(
        "findPackages",
        PACKAGES_TABLE_QUERY_WITH_BRAND,
        {"first": PAGE_SIZE, "where": {}},
        credentials_path=cp,
    )
    hits = []
    for node in pkgs:
        pr = node.get("Product") or {}
        bd = pr.get("Brand")
        bn = bd.get("Name") if isinstance(bd, dict) else ""
        nm = (pr.get("Name") or "").lower()
        if "stix" in nm or "xtrax" in nm:
            hits.append(
                (
                    bn,
                    pr.get("Name"),
                    node.get("SKU"),
                    pr.get("SKU"),
                    node.get("CurrentQty"),
                )
            )
    print(f"packages={len(pkgs)} stix|xtrax in product name: {len(hits)}")
    for h in sorted(set(hits))[:80]:
        print(h)


if __name__ == "__main__":
    main()
