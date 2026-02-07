from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


@dataclass
class InstanceRow:
    instance_id: str
    company_key: str
    active_years: str
    last_tick_at: str
    last_post_at: str
    last_post_ok: str
    cells_written: int
    rows_marked_true: int
    skipped_no_rule: int
    last_error: str


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None


def discover_heartbeat_files() -> List[Path]:
    # Preferred (instance isolation) layout:
    #   .kylo/instances/<id>/health/heartbeat.json
    roots = []
    inst_root = Path(".kylo") / "instances"
    if inst_root.exists():
        for d in inst_root.iterdir():
            if d.is_dir():
                p = d / "health" / "heartbeat.json"
                if p.exists():
                    roots.append(p)

    # Legacy layout fallback:
    legacy = Path(".kylo") / "health"
    if legacy.exists():
        for p in legacy.glob("*.json"):
            if p.is_file():
                roots.append(p)

    # De-dupe while preserving order
    out: List[Path] = []
    seen = set()
    for p in roots:
        rp = str(p.resolve())
        if rp not in seen:
            out.append(p)
            seen.add(rp)
    return out


def heartbeat_to_row(hb: Dict[str, Any]) -> InstanceRow:
    instance_id = str(hb.get("instance_id") or "")
    company_key = str(hb.get("company_key") or "").strip().upper()
    if not company_key and instance_id:
        # Best-effort: infer from instance_id format (JGD_2025 or JGD:2025)
        raw = instance_id.split(":", 1)[0].split("_", 1)[0]
        company_key = raw.strip().upper()
    years = hb.get("active_years")
    if isinstance(years, list):
        active_years = ",".join(str(y) for y in years)
    else:
        active_years = ""

    last_tick_at = str(hb.get("last_tick_at") or "")
    last_post_at = str(hb.get("last_post_finished_at") or hb.get("last_post_started_at") or "")
    last_post_ok_val = hb.get("last_post_ok")
    last_post_ok = "" if last_post_ok_val is None else ("true" if bool(last_post_ok_val) else "false")

    summary = hb.get("last_post_summary") or {}
    if not isinstance(summary, dict):
        summary = {}
    cells_written = int(summary.get("cells_written", 0) or 0)
    rows_marked_true = int(summary.get("rows_marked_true", 0) or 0)
    skipped_no_rule = int(summary.get("skipped_no_rule", 0) or 0)

    last_error = str(hb.get("last_error") or "")

    return InstanceRow(
        instance_id=instance_id,
        company_key=company_key,
        active_years=active_years,
        last_tick_at=last_tick_at,
        last_post_at=last_post_at,
        last_post_ok=last_post_ok,
        cells_written=cells_written,
        rows_marked_true=rows_marked_true,
        skipped_no_rule=skipped_no_rule,
        last_error=last_error,
    )


def build_dashboard() -> Dict[str, Any]:
    rows: List[InstanceRow] = []
    for p in discover_heartbeat_files():
        hb = _read_json(p)
        if not hb:
            continue
        try:
            rows.append(heartbeat_to_row(hb))
        except Exception:
            continue

    # Sort by instance_id for stable output
    rows.sort(key=lambda r: r.instance_id)

    return {
        "schema_version": 1,
        "updated_at": _utc_now_iso(),
        "instances": [
            {
                "instance_id": r.instance_id,
                "company_key": r.company_key,
                "active_years": r.active_years,
                "last_tick_at": r.last_tick_at,
                "last_post_at": r.last_post_at,
                "last_post_ok": r.last_post_ok,
                "cells_written": r.cells_written,
                "rows_marked_true": r.rows_marked_true,
                "skipped_no_rule": r.skipped_no_rule,
                "last_error": r.last_error,
            }
            for r in rows
        ],
    }


def write_dashboard_json(path: Path | None = None) -> Path:
    if path is None:
        path = Path(".kylo") / "ops" / "dashboard.json"
    payload = build_dashboard()
    _atomic_write_json(path, payload)
    return path

