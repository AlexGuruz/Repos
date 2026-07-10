#!/usr/bin/env python3
"""
Introspect GrowFlow Retail GraphQL schema for priority query fields.

Uses the same auth and URL resolution as lib.growflow_graphql (credentials file or env).

Outputs (default):
  - data/growflow_schema_introspection.json  (gitignored; run locally)
  - docs/GROWFLOW_RETAIL_SCHEMA_MAP.md       (--write-docs)

Usage (repo root):
  PYTHONPATH=. python scripts/introspect_growflow_schema.py --growflow-credentials E:/secrets/gcp/growflowapi.txt
  PYTHONPATH=. python scripts/introspect_growflow_schema.py --write-docs

Requires GROWFLOW_RETAIL_ORG or GROWFLOW_GRAPHQL_URL for Retail endpoint.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.growflow_graphql import graphql_request, resolve_graphql_url
from lib.growflow_queries import (
    ORDER_ITEMS_QUERY,
    ORDER_ITEMS_QUERY_NO_BRAND,
    PACKAGES_TABLE_QUERY,
    PACKAGES_TABLE_QUERY_WITH_BRAND,
)

# Shallow __Type (3 ofType levels — enough for NON_NULL -> LIST -> OBJECT)
_TYPE_REF = """kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType { kind name }
            }
          }"""

# Single operation only (some servers reject multi-operation documents without operationName)
QUERY_ROOT_INTROSPECTION = (
    """
query IntrospectQueryRoot {
  __schema {
    queryType {
      fields {
        name
        description
        args {
          name
          description
          type {
"""
    + _TYPE_REF
    + """
          }
        }
        type {
"""
    + _TYPE_REF
    + """
        }
      }
    }
  }
}
"""
)

# Priority + existing implementations (partner doc may use different root names)
PRIORITY_FIELDS = frozenset(
    {
        "findProducts",
        "findBrands",
        "findProductCategories",
        "findTransfers",
        "findTransactions",
        "findStores",
        "findOrderItems",
        "findPackages",
        "preorderStatus",
        "findMenus",
        "createPreorder",
    }
)


def _load_org_from_config() -> None:
    if (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip():
        return
    cfg = REPO / "config" / "config.yaml"
    if not cfg.is_file():
        return
    text = cfg.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^\s*org_id:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if m:
        os.environ["GROWFLOW_RETAIL_ORG"] = m.group(1).strip().strip("\"'")


def unwrap_named_type(t: dict[str, Any] | None) -> str | None:
    """Walk ofType chain to the innermost named type."""
    cur = t
    while cur:
        name = cur.get("name")
        if name:
            return str(name)
        cur = cur.get("ofType")
    return None


def type_to_string(t: dict[str, Any] | None) -> str:
    """Print a type ref as e.g. [Product!]!"""
    if not t:
        return "?"
    kind = t.get("kind")
    inner = t.get("ofType")
    if kind == "NON_NULL":
        return type_to_string(inner) + "!"
    if kind == "LIST":
        return "[" + type_to_string(inner) + "]"
    if kind in ("SCALAR", "OBJECT", "INTERFACE", "ENUM", "INPUT_OBJECT", "UNION"):
        return t.get("name") or kind or "?"
    return str(t.get("name") or kind or "?")


def _credentials_path(cli: str | None) -> str | None:
    p = (cli or os.environ.get("GROWFLOW_CREDENTIALS_PATH") or "").strip()
    if p:
        return p
    f = Path("E:/secrets/gcp/growflowapi.txt")
    return str(f) if f.is_file() else None


def fetch_query_root_fields(creds: str | None) -> list[dict[str, Any]]:
    resp = graphql_request(QUERY_ROOT_INTROSPECTION.strip(), credentials_path=creds)
    errs = resp.get("errors")
    if errs:
        raise RuntimeError(errs[0].get("message", str(errs)))
    data = resp.get("data") or {}
    schema = data.get("__schema") or {}
    qt = schema.get("queryType") or {}
    return list(qt.get("fields") or [])


def fetch_type_definition(creds: str | None, type_name: str) -> dict[str, Any] | None:
    q2 = """
query IntrospectType($name: String!) {
  __type(name: $name) {
    name
    kind
    description
    fields {
      name
      description
      args {
        name
        description
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType { kind name }
            }
          }
        }
      }
      type {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType { kind name }
          }
        }
      }
    }
    inputFields {
      name
      description
      type {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType { kind name }
          }
        }
      }
    }
  }
}
"""
    resp = graphql_request(q2, {"name": type_name}, credentials_path=creds)
    errs = resp.get("errors")
    if errs:
        return None
    return (resp.get("data") or {}).get("__type")


def collect_related_type_names(field: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    ret = field.get("type")
    n = unwrap_named_type(ret)
    if n:
        names.add(n)
    for a in field.get("args") or []:
        tn = unwrap_named_type((a.get("type") or {}))
        if tn and not tn.startswith("__"):
            names.add(tn)
    return names


def expand_types_bfs(
    creds: str | None,
    seed_names: set[str],
    *,
    max_types: int = 60,
) -> dict[str, Any]:
    """BFS expand OBJECT/INTERFACE types referenced from seed."""
    out: dict[str, Any] = {}
    seen: set[str] = set()
    q: deque[str] = deque()
    for s in sorted(seed_names):
        if s and not s.startswith("__"):
            q.append(s)
    while q and len(out) < max_types:
        name = q.popleft()
        if name in seen:
            continue
        seen.add(name)
        info = fetch_type_definition(creds, name)
        if not info or info.get("kind") not in ("OBJECT", "INTERFACE", "INPUT_OBJECT"):
            continue
        out[name] = info
        for f in info.get("fields") or []:
            tn = unwrap_named_type(f.get("type"))
            if tn and tn not in seen and not tn.startswith("__"):
                q.append(tn)
        for inf in info.get("inputFields") or []:
            tn = unwrap_named_type(inf.get("type"))
            if tn and tn not in seen and not tn.startswith("__"):
                q.append(tn)
    return out


def build_summary(
    all_fields: list[dict[str, Any]],
    expanded: dict[str, Any],
) -> dict[str, Any]:
    by_name = {f["name"]: f for f in all_fields}
    priority: dict[str, Any] = {}
    for name in sorted(PRIORITY_FIELDS):
        if name not in by_name:
            priority[name] = {"present": False}
            continue
        f = by_name[name]
        priority[name] = {
            "present": True,
            "description": (f.get("description") or "").strip(),
            "return_type": type_to_string(f.get("type")),
            "return_named": unwrap_named_type(f.get("type")),
            "args": [
                {
                    "name": a.get("name"),
                    "description": (a.get("description") or "").strip(),
                    "type": type_to_string(a.get("type")),
                }
                for a in (f.get("args") or [])
            ],
        }
    other_find = sorted(
        x["name"] for x in all_fields if x.get("name", "").startswith("find") and x["name"] not in PRIORITY_FIELDS
    )
    return {
        "priority": priority,
        "other_find_queries": other_find[:200],
        "expanded_type_count": len(expanded),
        "expanded_type_names": sorted(expanded.keys()),
    }


def render_schema_map_md(
    summary: dict[str, Any],
    expanded: dict[str, Any],
    graphql_url: str,
    generated_at: str,
) -> str:
    lines: list[str] = [
        "# GrowFlow Retail GraphQL — schema map (introspected)",
        "",
        "**Doc index:** `docs/GROWFLOW_API.md` — **next data to request:** `docs/GROWFLOW_NEXT_DATA_REQUEST.md` "
        "— **discovery harness:** `scripts/run_growflow_discovery_queries.py`",
        "",
        f"**Generated:** {generated_at} UTC",
        f"**Endpoint:** `{graphql_url}`",
        "",
        "> Source: live `__schema` introspection via `scripts/introspect_growflow_schema.py`. "
        "Re-run after GrowFlow schema changes. The partner TXT doc is not authoritative.",
        "",
        "## Priority queries",
        "",
        "| Present | Query | Return type | Business purpose | Planner: SKU | Brand | Category | Store | Transfers | Tender |",
        "| :--: | --- | --- | --- | :--: | :--: | :--: | :--: | :--: | :--: |",
    ]
    purpose_row: dict[str, tuple[str, str, str, str, str, str, str, str]] = {
        "findProducts": ("Product catalog / SKUs", "Y", "via Product", "via Product", "—", "—", "—", "—"),
        "findBrands": ("Brand master", "—", "Y", "—", "—", "—", "—", "—"),
        "findProductCategories": ("Category taxonomy", "—", "—", "Y", "—", "—", "—", "—"),
        "findTransfers": ("Inter-location inventory moves", "—", "—", "—", "—", "Y", "—", "—"),
        "findTransactions": ("Tender / payments", "—", "—", "—", "—", "—", "—", "Y"),
        "findStores": ("Locations / scope", "—", "—", "—", "Y", "—", "—", "—"),
        "findOrderItems": ("Sold lines (implemented)", "line-level", "inferred", "inferred", "—", "—", "—", "—"),
        "findPackages": ("Inventory packages (implemented)", "package/SKU", "—", "—", "—", "—", "—", "—"),
        "preorderStatus": ("Preorder order status", "—", "—", "—", "—", "—", "—", "—"),
        "findMenus": ("Menu / POS menu tree", "—", "—", "—", "—", "—", "—", "—"),
        "createPreorder": ("Mutation: create preorder", "—", "—", "—", "—", "—", "—", "—"),
    }
    for qname in sorted(PRIORITY_FIELDS):
        meta = summary["priority"].get(qname) or {}
        if not meta.get("present"):
            lines.append(f"| **no** | `{qname}` | — | *Not exposed on Query root* | — | — | — | — | — | — |")
            continue
        rt = meta.get("return_type", "?")
        purp = purpose_row.get(qname, ("See description", "?", "?", "?", "?", "?", "?", "?"))[0]
        flags = purpose_row.get(qname, ("", "—", "—", "—", "—", "—", "—", "—"))[1:]
        lines.append(
            f"| **yes** | `{qname}` | `{rt}` | {purp} | {flags[0]} | {flags[1]} | {flags[2]} | {flags[3]} | {flags[4]} | {flags[5]} |"
        )
    lines.extend(
        [
            "",
            "### Arguments (priority queries)",
            "",
        ]
    )
    for qname in sorted(PRIORITY_FIELDS):
        meta = summary["priority"].get(qname) or {}
        if not meta.get("present"):
            continue
        lines.append(f"#### `{qname}`")
        desc = meta.get("description")
        if desc:
            lines.append(f"- *Description:* {desc}")
        lines.append(f"- *Returns:* `{meta.get('return_type')}`")
        args = meta.get("args") or []
        if not args:
            lines.append("- *Args:* (none)")
        else:
            lines.append("- *Args:*")
            for a in args:
                lines.append(f"  - `{a['name']}`: `{a['type']}`")
        lines.append("")

    lines.extend(
        [
            "## Other `find*` operations on Query (names only)",
            "",
            "Use these to discover additional connections not listed above:",
            "",
            "```text",
        ]
    )
    lines.extend(summary.get("other_find_queries") or ["(none)"])
    lines.extend(["```", "", "## Expanded types (fields)", ""])

    for tname in sorted(expanded.keys()):
        info = expanded[tname]
        lines.append(f"### `{tname}` ({info.get('kind')})")
        d = (info.get("description") or "").strip()
        if d:
            lines.append(f"{d}")
        fields = info.get("fields") or []
        if fields:
            lines.append("| Field | Type | Description |")
            lines.append("| --- | --- | --- |")
            for f in fields[:120]:
                fn = f.get("name", "")
                ts = type_to_string(f.get("type"))
                ds = ((f.get("description") or "").replace("|", "\\|").replace("\n", " ")[:120])
                lines.append(f"| `{fn}` | `{ts}` | {ds} |")
            if len(fields) > 120:
                lines.append(f"| … | | *({len(fields) - 120} more fields)* |")
        inps = info.get("inputFields") or []
        if inps:
            lines.append("")
            lines.append("**Input fields:**")
            lines.append("| Field | Type |")
            lines.append("| --- | --- |")
            for inf in inps:
                lines.append(f"| `{inf.get('name')}` | `{type_to_string(inf.get('type'))}` |")
        lines.append("")

    lines.extend(
        [
            "## Sample discovery queries",
            "",
            "Replace variables with real IDs from your org. Use the playground or `graphql_request` after auth.",
            "",
            "```graphql",
            "# Products (adjust args to match schema — see Args section above)",
            "query Sample {",
            "  findProducts(first: 5) {",
            "    edges { node { objectId name SKU } }",
            "    pageInfo { hasNextPage }",
            "  }",
            "}",
            "```",
            "",
            "```graphql",
            "query Sample {",
            "  findBrands(first: 20) { edges { node { objectId name } } }",
            "}",
            "```",
            "",
            "```graphql",
            "query Sample {",
            "  findProductCategories(first: 50) { edges { node { objectId name } } }",
            "}",
            "```",
            "",
            "```graphql",
            "query Sample {",
            "  findStores(first: 20) { edges { node { objectId name } } }",
            "}",
            "```",
            "",
            "*If a field name errors, use this document’s expanded `*Type` tables and the playground to fix selections.*",
            "",
        ]
    )
    return "\n".join(lines)


def render_fallback_schema_map_md(graphql_url: str, error_hint: str, generated_at: str) -> str:
    """
    When production Retail disables __schema/__type introspection (common), still emit a useful map:
    implemented queries from repo + discovery templates + next steps.
    """
    lines: list[str] = [
        "# GrowFlow Retail GraphQL — schema map",
        "",
        "**Doc index:** `docs/GROWFLOW_API.md` — **next data to request:** `docs/GROWFLOW_NEXT_DATA_REQUEST.md` "
        "— **discovery harness:** `scripts/run_growflow_discovery_queries.py`",
        "",
        f"**Generated:** {generated_at} UTC",
        f"**Endpoint tested:** `{graphql_url}`",
        "",
        "## Introspection status",
        "",
        "Live `__schema` / `__type` introspection **failed** for this endpoint (typical for production Retail).",
        "",
        f"> Error: `{error_hint[:500]}`",
        "",
        "**What to do:**",
        "",
        "1. Open the **integrations** playground (`https://retail.growflow.com/c/integrations/graphql`) if GrowFlow gave you access, paste the introspection document from GraphiQL “Docs” or run this script with `GROWFLOW_GRAPHQL_URL` pointed there.",
        "2. Or export the schema from the playground’s **schema** tab / SDL and commit a redacted fragment under `docs/` if policy allows.",
        "3. Until then, treat field names in **sample** queries below as **hypotheses** — confirm each selection in the playground for your org.",
        "4. Doc index: `docs/GROWFLOW_API.md`. Partner data checklist: `docs/GROWFLOW_NEXT_DATA_REQUEST.md`. Quick probe: `python scripts/run_growflow_discovery_queries.py`.",
        "",
        "---",
        "",
        "## Implemented in this repo (exact queries)",
        "",
        "These are **not guessed** — they ship in `lib/growflow_queries.py` and power the buy planner, inventory, and BI scripts.",
        "",
        "### `findOrderItems` (with `Product.Brand`)",
        "",
        "```graphql",
        ORDER_ITEMS_QUERY.strip(),
        "```",
        "",
        "### `findOrderItems` (no Brand — schema fallback)",
        "",
        "```graphql",
        ORDER_ITEMS_QUERY_NO_BRAND.strip(),
        "```",
        "",
        "### `findPackages`",
        "",
        "```graphql",
        PACKAGES_TABLE_QUERY.strip(),
        "```",
        "",
        "### `findPackages` (with `Product.Brand`)",
        "",
        "```graphql",
        PACKAGES_TABLE_QUERY_WITH_BRAND.strip(),
        "```",
        "",
        "---",
        "",
        "## Priority queries to confirm in playground (not introspected here)",
        "",
        "| Query | Planner use | Sample shape (validate fields!) |",
        "| --- | --- | --- |",
        "| `findProducts` | SKU / product identity, brand+category linkage | `findProducts(first: 5) { edges { node { objectId name SKU } } pageInfo { hasNextPage } }` |",
        "| `findBrands` | Normalize brand dimension | `findBrands(first: 50) { edges { node { objectId name } } }` |",
        "| `findProductCategories` | Replace inferred categories | `findProductCategories(first: 100) { edges { node { objectId name } } }` |",
        "| `findTransfers` | Inter-store movement vs sales | `findTransfers(first: 20) { edges { node { objectId } } }` — *expand node fields from docs* |",
        "| `findTransactions` | Tender vs order-total checks | `findTransactions(first: 20) { edges { node { objectId } } }` — *expand from docs* |",
        "| `findStores` | Multi-store scope | `findStores(first: 20) { edges { node { objectId name } } }` |",
        "| `preorderStatus` | Preorder flow | `query { preorderStatus(orderId: \"…\") { order { id status orderNumber } } }` |",
        "| `findMenus` | Partner doc sample | `findMenus(menuKey: \"…\") { menuGroups { name products { name sku } } }` |",
        "",
        "Connection pattern is usually `edges { node { … } }`, `pageInfo { hasNextPage endCursor }`, and `count` — match your live schema.",
        "",
        "---",
        "",
        "## Re-run introspection when allowed",
        "",
        "```bash",
        "PYTHONPATH=. python scripts/introspect_growflow_schema.py --write-docs \\",
        "  --growflow-credentials E:/secrets/gcp/growflowapi.txt",
        "# Optional: integrations sandbox",
        "# set GROWFLOW_GRAPHQL_URL=https://retail.growflow.com/c/integrations/graphql",
        "```",
        "",
        "Successful runs write `data/growflow_schema_introspection.json` (gitignored) and replace this file’s introspected tables when `--write-docs` is used with a working endpoint.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Introspect GrowFlow Retail GraphQL schema")
    ap.add_argument("--growflow-credentials", default=None, help="Path to GrowFlow credentials file")
    ap.add_argument(
        "--graphql-url",
        default=None,
        help="Override GraphQL URL (else GROWFLOW_GRAPHQL_URL or retail org)",
    )
    ap.add_argument(
        "--write-docs",
        action="store_true",
        help=f"Write {REPO / 'docs' / 'GROWFLOW_RETAIL_SCHEMA_MAP.md'}",
    )
    ap.add_argument(
        "--json-out",
        type=Path,
        default=REPO / "data" / "growflow_schema_introspection.json",
        help="Write raw bundle JSON (default: data/growflow_schema_introspection.json)",
    )
    ap.add_argument("--max-expanded-types", type=int, default=55)
    args = ap.parse_args()

    _load_org_from_config()
    creds = _credentials_path(args.growflow_credentials)

    if args.graphql_url:
        os.environ["GROWFLOW_GRAPHQL_URL"] = args.graphql_url.strip()

    url = resolve_graphql_url(args.graphql_url)

    if not creds and not (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip():
        print(
            "No credentials: set --growflow-credentials, GROWFLOW_CREDENTIALS_PATH, or GROWFLOW_ACCESS_TOKEN.",
            file=sys.stderr,
        )
        print(f"Endpoint would be: {url}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        all_fields = fetch_query_root_fields(creds)
    except Exception as e:
        err = str(e)
        print(f"Warning: introspection failed ({err}). Writing fallback docs if requested.", flush=True)
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now,
                    "graphql_url": url,
                    "introspection_disallowed": True,
                    "error": err,
                    "note": "Production Retail often returns HTTP 400 for __schema/__type. Use integrations playground or exported SDL.",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {args.json_out.resolve()} (fallback)", flush=True)
        if args.write_docs:
            md_path = REPO / "docs" / "GROWFLOW_RETAIL_SCHEMA_MAP.md"
            md_path.write_text(render_fallback_schema_map_md(url, err, now), encoding="utf-8")
            print(f"Wrote {md_path.resolve()} (fallback)", flush=True)
        return 0

    by_name = {f["name"]: f for f in all_fields}
    seed: set[str] = set()
    for name in PRIORITY_FIELDS:
        if name in by_name:
            seed |= collect_related_type_names(by_name[name])

    expanded = expand_types_bfs(creds, seed, max_types=args.max_expanded_types)
    summary = build_summary(all_fields, expanded)

    bundle = {
        "generated_at_utc": now,
        "graphql_url": url,
        "introspection_disallowed": False,
        "summary": summary,
        "query_root_field_names": sorted(f["name"] for f in all_fields),
        "expanded_types": expanded,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    print(f"Wrote {args.json_out.resolve()}", flush=True)

    if args.write_docs:
        md_path = REPO / "docs" / "GROWFLOW_RETAIL_SCHEMA_MAP.md"
        md_path.write_text(
            render_schema_map_md(summary, expanded, url, now),
            encoding="utf-8",
        )
        print(f"Wrote {md_path.resolve()}", flush=True)

    missing = [n for n in sorted(PRIORITY_FIELDS) if not summary["priority"].get(n, {}).get("present")]
    if missing:
        print("Note: not on Query root:", ", ".join(missing), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
