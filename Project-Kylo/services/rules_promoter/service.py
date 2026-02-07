from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import psycopg2


def _slugify(company_id: str) -> str:
    import re
    s = re.sub(r"[^A-Za-z0-9]+", "_", company_id.strip().lower())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "company"


def _ensure_global_snapshot_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
CREATE SCHEMA IF NOT EXISTS control;
CREATE TABLE IF NOT EXISTS control.rules_snapshots (
  snapshot_id        BIGSERIAL PRIMARY KEY,
  company_id         TEXT NOT NULL,
  version            BIGINT NOT NULL,
  snapshot           JSONB NOT NULL,
  snapshot_checksum  TEXT NOT NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (company_id, version)
);
"""
        )


def _compute_company_checksum(conn) -> Optional[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
SELECT 'md5:' || md5(coalesce(string_agg(rule_id::text || '|' || md5(rule_json::text), E'\n' ORDER BY rule_id), '')) AS checksum
FROM app.rules_active;
"""
        )
        r = cur.fetchone()
        return r[0] if r else None


def _active_count(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM app.rules_active;")
        return int(cur.fetchone()[0])


def _compute_snapshot_checksum(snapshot: List[Tuple[str, dict]]) -> str:
    """Replicate the DB checksum formula:
    md5(string_agg(rule_id || '|' || md5(rule_json::text) ORDER BY rule_id))
    where rule_id = uuid5(NAMESPACE_URL, content_hash)
    """
    import uuid as _uuid
    import hashlib as _hashlib
    rows: List[Tuple[str, str]] = []
    for content_hash, rule_json in snapshot:
        rid = str(_uuid.uuid5(_uuid.NAMESPACE_URL, content_hash))
        rj_txt = json.dumps(rule_json, separators=(",", ":"))
        inner = _hashlib.md5(rj_txt.encode("utf-8")).hexdigest()
        rows.append((rid, inner))
    rows.sort(key=lambda x: x[0])
    concat = "\n".join(f"{rid}|{inner}" for (rid, inner) in rows)
    return "md5:" + _hashlib.md5(concat.encode("utf-8")).hexdigest()


def _fetch_pending_approved(conn, table_name: str) -> List[Tuple[str, dict]]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
SELECT content_hash, jsonb_build_object(
  'source', source,
  'target_sheet', target_sheet,
  'target_header', target_header,
  'approved', true
) AS rule_json
FROM {table_name}
WHERE approved = true
ORDER BY content_hash
"""
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def _apply_snapshot_to_company(conn, snapshot: List[Tuple[str, dict]]) -> None:
    with conn.cursor() as cur:
        cur.execute("TRUNCATE app.rules_active;")
        # Convert to arrays for UNNEST insert
        import uuid as _uuid
        rule_ids = []
        rule_jsons = []
        for ch, rj in snapshot:
            rule_ids.append(str(_uuid.uuid5(_uuid.NAMESPACE_URL, ch)))
            rule_jsons.append(json.dumps(rj))
        cur.execute(
            """
WITH src AS (
  SELECT * FROM unnest(%(rule_id)s::uuid[], %(rule_json)s::jsonb[]) AS t(rule_id, rule_json)
)
INSERT INTO app.rules_active (rule_id, rule_json, applied_at)
SELECT rule_id, rule_json, now() FROM src
ON CONFLICT (rule_id) DO UPDATE SET rule_json = EXCLUDED.rule_json, applied_at = now();
""",
            {"rule_id": rule_ids, "rule_json": rule_jsons},
        )


def _sheets_writeback(company_id: str, promoted_count: int) -> Optional[str]:
    try:
        import os as _os
        from services.rules_loader.sheets_loader import _load_sheets_service, _extract_spreadsheet_id
        from scaffold.tools.sheets_cli import load_companies_config
        from scaffold.tools.sheets_cli import resolve_spreadsheet_id as _resolve

        # Use the rules management workbook, not the company transaction workbook
        # This is the correct spreadsheet for rule management
        sid = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
        sa_path = _os.environ.get("KYLO_SHEETS_SA", _os.path.join("secrets", "service_account.json"))
        if not _os.path.exists(sa_path):
            return "skipped: no service account"
        service = _load_sheets_service(sa_path)

        # Append a small banner row to the company's Pending tab indicating promotion
        # Use the new tab naming convention: "{company_id} Pending"
        title = f"{company_id} Pending"
        meta = service.spreadsheets().get(spreadsheetId=sid).execute()
        tab_id = None
        for s in meta.get("sheets", []):
            props = s.get("properties", {})
            if props.get("title") == title:
                tab_id = int(props.get("sheetId"))
                break
        if tab_id is None:
            return "skipped: pending tab missing"

        from datetime import datetime as _dt
        msg = f"Promoted {promoted_count} rule(s) to Active at {_dt.utcnow().isoformat(timespec='seconds')}Z"

        def _cell(v: str) -> Dict[str, str]:
            return {"userEnteredValue": {"stringValue": v}}
        body = {
            "requests": [
                {  # append a single full-width note row at the bottom
                    "appendCells": {
                        "sheetId": tab_id,
                        "rows": [{"values": [_cell(msg)]}],
                        "fields": "userEnteredValue",
                    }
                }
            ]
        }
        service.spreadsheets().batchUpdate(spreadsheetId=sid, body=body).execute()
        return "ok"
    except Exception as e:  # best-effort, do not fail promotion
        return f"skipped: {e}"


def promote(global_dsn: Optional[str], company_dsn_map: Dict[str, str], companies: Optional[List[str]] = None) -> Dict[str, str]:
    results: Dict[str, str] = {}
    gconn = None
    if global_dsn:
        try:
            gconn = psycopg2.connect(global_dsn)
            gconn.autocommit = False
            _ensure_global_snapshot_table(gconn)
        except Exception as e:
            gconn = None
            results["__global__"] = f"global skipped: {e}"
    try:
        for company_id, company_dsn in company_dsn_map.items():
            if companies and company_id not in companies:
                continue
            table = f"rules_pending_{_slugify(company_id)}"
            try:
                # 1) Pull approved pending from company DB
                with psycopg2.connect(company_dsn) as cconn:
                    cconn.autocommit = False
                    with cconn.cursor() as cur:
                        cur.execute("SELECT to_regclass(%s)", (table,))
                        exists = cur.fetchone()[0] is not None
                    if not exists:
                        results[company_id] = "pending table missing"
                        cconn.rollback()
                        continue
                    snapshot = _fetch_pending_approved(cconn, table)
                    if not snapshot:
                        cconn.rollback()
                        results[company_id] = "no approved pending; skipped"
                        continue
                    _apply_snapshot_to_company(cconn, snapshot)
                    checksum = _compute_company_checksum(cconn)
                    count_after = _active_count(cconn)
                    cconn.commit()
                # Compute expected checksum from the snapshot we just applied
                expected_checksum = _compute_snapshot_checksum(snapshot)

                # 2) bump version + record snapshot in global (if available)
                version = 1
                if gconn is not None:
                    with gconn.cursor() as cur:
                        cur.execute(
                            """
INSERT INTO control.company_rules_version(company_id, version, updated_at)
VALUES (%(company_id)s, 1, now())
ON CONFLICT (company_id) DO UPDATE SET version = control.company_rules_version.version + 1, updated_at = now()
RETURNING version;
""",
                            {"company_id": company_id},
                        )
                        version = int(cur.fetchone()[0])
                        cur.execute(
                            """
INSERT INTO control.rules_snapshots(company_id, version, snapshot, snapshot_checksum)
VALUES (%(company_id)s, %(version)s, %(snapshot)s::jsonb, %(checksum)s)
ON CONFLICT (company_id, version) DO NOTHING;
""",
                            {
                                "company_id": company_id,
                                "version": version,
                                "snapshot": json.dumps([{"rule_id": h, "rule_json": rj} for h, rj in snapshot]),
                                "checksum": checksum,
                            },
                        )
                    gconn.commit()
                # Optional prune of approved pending
                pruned_note = ""
                try:
                    # Always attempt prune, but only after confirmation: count and checksum must match expected
                    if count_after == len(snapshot) and checksum and checksum == expected_checksum:
                        with psycopg2.connect(company_dsn) as cconn2:
                            with cconn2.cursor() as cur2:
                                cur2.execute(f"DELETE FROM {table} WHERE approved = true;")
                            cconn2.commit()
                        pruned_note = "; pruned approved pending"
                    else:
                        pruned_note = "; prune skipped (confirmation failed)"
                except Exception:
                    pruned_note = "; prune skipped (error)"

                # Best-effort Sheets writeback
                wb = _sheets_writeback(company_id, len(snapshot))
                note = f" (sheets: {wb})" if wb else ""
                results[company_id] = f"promoted version {version} with {len(snapshot)} rules{pruned_note}{note}"
            except Exception as e:
                if gconn is not None:
                    gconn.rollback()
                results[company_id] = f"error: {e}"
    finally:
        if gconn is not None:
            try:
                gconn.close()
            except Exception:
                pass
    return results


