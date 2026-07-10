"""
Flatten **Accepted** (or other status) **findTransfers** nodes into receipt rows for cohort metrics.

Each row is one **transfer package line** with:

- ``received_at`` — transfer ``ReceivedAt`` (ISO UTC from Growflow). Use as the inventory **landed**
  timestamp for sell-through windows (compare to ``OrderItems.SoldAt``).
- ``received_at_epoch_ms`` / ``received_date_local`` — convenience for spreadsheets, Kylo ETL, and
  aligning to **store calendar** (from ``sales_timezone`` / ``GROWFLOW_SALES_TZ``).

**Joining to sales (Growflow repo):** for receipt-cohort sell-through, match
``OrderItems.Package.objectId`` to transfer ``Packages.objectId`` (see
``scripts/transfer_cohort_sellthrough.py``). Product-level joins use ``product_object_id`` when
present, else ``product_name`` + ``brand_name``. **Do not** treat ``OrderItems.OriginId`` as package
``objectId`` (compliance tag; see ``scripts/_cartel_7pk_first_receipt_sellout.py`` docstring).

**Kylo / company_bi:** use ``received_date_local`` or UTC day buckets to align trailing COG with
cash expense timing (Sheets / ``KYLO_GLOBAL_DSN`` paths described in ``company_bi/docs``).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone, tzinfo
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lib.growflow_graphql import graphql_request

TRANSFER_RECEIPTS_QUERY = """
query TransferReceipts($first: Int!, $status: String!) {
  findTransfers(first: $first, order: [ReceivedAt_DESC], where: { Status: { equalTo: $status } }) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        createdAt
        updatedAt
        FromName
        Store { objectId Name }
        ReceivingStore { objectId Name }
        Packages {
          ... on Packages {
            objectId
            SKU
            OriginalQty
            CurrentQty
            Cost
            Product {
              objectId
              Name
              SKU
              Brand { Name }
            }
          }
        }
      }
    }
  }
}
"""

TRANSFER_RECEIPTS_PAGED_QUERY = """
query TransferReceiptsPaged($first: Int!, $after: String, $where: TransfersWhereInput) {
  findTransfers(first: $first, after: $after, order: [ReceivedAt_DESC], where: $where) {
    edges {
      node {
        objectId
        Status
        ReceivedAt
        createdAt
        updatedAt
        FromName
        Store { objectId Name }
        ReceivingStore { objectId Name }
        Packages {
          ... on Packages {
            objectId
            SKU
            OriginalQty
            CurrentQty
            Cost
            Product {
              objectId
              Name
              SKU
              Brand { Name }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""

SCHEMA_VERSION = 1


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def load_retail_org_from_config() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    p = _root() / "config" / "config.yaml"
    if not p.is_file():
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    org = _yaml_scalar(text, "org_id")
    if org:
        os.environ["GROWFLOW_RETAIL_ORG"] = org


def store_zoneinfo() -> ZoneInfo | tzinfo:
    name = (os.environ.get("GROWFLOW_SALES_TZ") or "").strip()
    if not name:
        p = _root() / "config" / "config.yaml"
        if p.is_file():
            name = (_yaml_scalar(p.read_text(encoding="utf-8", errors="replace"), "sales_timezone") or "").strip()
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return datetime.now(timezone.utc).astimezone().tzinfo or timezone.utc


def parse_received_at_utc(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_transfer_nodes(
    *,
    first: int,
    status: str,
    credentials_path: str | None,
) -> list[dict[str, Any]]:
    r = graphql_request(
        TRANSFER_RECEIPTS_QUERY,
        {"first": int(first), "status": str(status)},
        credentials_path=credentials_path,
    )
    if r.get("errors"):
        raise RuntimeError(r["errors"][0].get("message", r["errors"]))
    edges = ((r.get("data") or {}).get("findTransfers") or {}).get("edges") or []
    return [e["node"] for e in edges if e.get("node")]


def fetch_transfer_nodes_since(
    *,
    received_at_gte: str,
    status: str = "Accepted",
    page_size: int = 100,
    credentials_path: str | None,
) -> list[dict[str, Any]]:
    """
    Fetch all transfers with ``ReceivedAt >= received_at_gte`` in ``ReceivedAt_DESC`` order.
    """
    out: list[dict[str, Any]] = []
    after: str | None = None
    while True:
        where = {
            "Status": {"equalTo": str(status)},
            "ReceivedAt": {"greaterThanOrEqualTo": str(received_at_gte)},
        }
        r = graphql_request(
            TRANSFER_RECEIPTS_PAGED_QUERY,
            {"first": int(page_size), "after": after, "where": where},
            credentials_path=credentials_path,
        )
        if r.get("errors"):
            raise RuntimeError(r["errors"][0].get("message", r["errors"]))
        conn = (r.get("data") or {}).get("findTransfers") or {}
        edges = conn.get("edges") or []
        out.extend([e["node"] for e in edges if e.get("node")])
        pi = conn.get("pageInfo") or {}
        if not pi.get("hasNextPage"):
            break
        after = pi.get("endCursor")
        if not after:
            break
    return out


def rows_from_transfer_node(
    node: dict[str, Any],
    *,
    org_slug: str,
    exported_at: datetime,
    store_tz: ZoneInfo | tzinfo,
) -> list[dict[str, Any]]:
    """Expand one transfer node into flat receipt rows (one row per package line)."""
    recv_raw = node.get("ReceivedAt")
    recv_dt = parse_received_at_utc(str(recv_raw) if recv_raw is not None else "")
    epoch_ms = int(recv_dt.timestamp() * 1000) if recv_dt else None
    local_date = recv_dt.astimezone(store_tz).date().isoformat() if recv_dt else None

    store = node.get("Store") if isinstance(node.get("Store"), dict) else {}
    recv_store = node.get("ReceivingStore") if isinstance(node.get("ReceivingStore"), dict) else {}
    tid = str(node.get("objectId") or "").strip()
    rows: list[dict[str, Any]] = []
    pkgs = node.get("Packages") or []
    for pkg in pkgs:
        if not isinstance(pkg, dict):
            continue
        pr = pkg.get("Product") if isinstance(pkg.get("Product"), dict) else {}
        br = pr.get("Brand") if isinstance(pr.get("Brand"), dict) else {}
        sku_pkg = pkg.get("SKU")
        sku_prod = pr.get("SKU")
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "org_slug": org_slug,
                "exported_at": exported_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "transfer_object_id": tid,
                "transfer_status": node.get("Status"),
                "transfer_created_at": node.get("createdAt"),
                "transfer_updated_at": node.get("updatedAt"),
                "received_at": str(recv_raw) if recv_raw else None,
                "received_at_epoch_ms": epoch_ms,
                "received_date_local": local_date,
                "sales_timezone": getattr(store_tz, "key", None) or str(store_tz),
                "from_name": node.get("FromName"),
                "store_object_id": store.get("objectId"),
                "store_name": store.get("Name"),
                "receiving_store_object_id": recv_store.get("objectId"),
                "receiving_store_name": recv_store.get("Name"),
                "package_object_id": str(pkg.get("objectId") or "").strip() or None,
                "package_sku": str(sku_pkg).strip() if sku_pkg is not None else None,
                "original_qty": int(pkg.get("OriginalQty") or 0),
                "current_qty": int(pkg.get("CurrentQty") or 0),
                "cost_cents": int(pkg.get("Cost") or 0),
                "product_object_id": str(pr.get("objectId") or "").strip() or None,
                "product_name": (str(pr.get("Name") or "").strip() or None),
                "product_sku": str(sku_prod).strip() if sku_prod is not None else None,
                "brand_name": (str(br.get("Name") or "").strip() or None),
            }
        )
    return rows


def fetch_transfer_receipt_rows(
    *,
    first: int = 50,
    skip: int = 0,
    status: str = "Accepted",
    credentials_path: str | None = None,
) -> list[dict[str, Any]]:
    """
    Pull transfer nodes (by ``ReceivedAt`` desc), skip the first ``skip`` nodes, then take ``first``
    nodes, and return flattened package rows.

    Example: ``skip=8, first=12`` returns package lines for transfers **9–20** (0-based skip after
    the eight most recent).
    """
    load_retail_org_from_config()
    org = (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip() or "unknown"
    store_tz = store_zoneinfo()
    exported_at = datetime.now(timezone.utc)
    skip_n = max(0, int(skip))
    take_n = max(0, int(first))
    nodes = fetch_transfer_nodes(
        first=skip_n + take_n,
        status=status,
        credentials_path=credentials_path,
    )
    nodes = nodes[skip_n : skip_n + take_n]
    out: list[dict[str, Any]] = []
    for n in nodes:
        out.extend(rows_from_transfer_node(n, org_slug=org, exported_at=exported_at, store_tz=store_tz))
    return out


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]], *, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
