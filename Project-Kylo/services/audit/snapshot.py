from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.audit.logger import write_diff_json
from services.audit.paths import latest_snapshot_link, snapshots_root
from services.audit.row_model import ChangeEvent, RowRecord


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def save_tick_snapshot(
    instance_id: str,
    *,
    csv_by_key: Dict[str, str],
    row_registry: Dict[str, RowRecord],
    events: List[ChangeEvent],
    meta: Dict[str, Any],
    watch_state_path: Optional[Path] = None,
    posting_state_path: Optional[Path] = None,
) -> Path:
    """Persist a timestamped snapshot directory and update snapshots_latest symlink/file."""
    stamp = _utc_stamp()
    snap_dir = snapshots_root(instance_id) / stamp
    snap_dir.mkdir(parents=True, exist_ok=True)

    sheets_dir = snap_dir / "sheets"
    sheets_dir.mkdir(exist_ok=True)
    for key, csv_text in csv_by_key.items():
        safe = key.replace("|", "__").replace("/", "_")
        (sheets_dir / f"{safe}.csv").write_text(csv_text, encoding="utf-8")

    reg_out = {k: v.to_dict() for k, v in row_registry.items()}
    (snap_dir / "row_registry.json").write_text(json.dumps(reg_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for label, src in (("watch_state.json", watch_state_path), ("posting_state.json", posting_state_path)):
        if src and Path(src).exists():
            shutil.copy2(src, snap_dir / label)

    diff_payload = {
        "ts": _utc_iso(),
        "instance_id": instance_id,
        "event_count": len(events),
        "events": [e.to_dict() for e in events],
        **meta,
    }
    write_diff_json(snap_dir / "diff.json", diff_payload)
    write_diff_json(snap_dir / "meta.json", {"ts": diff_payload["ts"], **meta})

    _update_latest_pointer(instance_id, snap_dir)
    return snap_dir


def _update_latest_pointer(instance_id: str, snap_dir: Path) -> None:
    link = latest_snapshot_link(instance_id)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        if link.is_symlink() or link.exists():
            link.unlink(missing_ok=True)
        link.symlink_to(snap_dir.resolve(), target_is_directory=True)
    except OSError:
        link.write_text(str(snap_dir.resolve()), encoding="utf-8")


def load_row_registry(path: Path) -> Dict[str, RowRecord]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: Dict[str, RowRecord] = {}
    if not isinstance(data, dict):
        return out
    for rk, raw in data.items():
        if not isinstance(raw, dict):
            continue
        try:
            out[str(rk)] = RowRecord(
                row_key=str(raw.get("row_key") or rk),
                source_spreadsheet_id=str(raw.get("source_spreadsheet_id") or ""),
                source_tab=str(raw.get("source_tab") or "TRANSACTIONS"),
                row_index_0based=int(raw.get("row_index_0based") or 0),
                company_id=str(raw.get("company_id") or ""),
                posted_date=str(raw.get("posted_date") or ""),
                description=str(raw.get("description") or ""),
                amount_cents=int(raw.get("amount_cents") or 0),
                posted_flag=bool(raw.get("posted_flag")),
                first_seen_at=str(raw.get("first_seen_at") or ""),
                content_fp=str(raw.get("content_fp") or ""),
                txn_uid=str(raw.get("txn_uid") or ""),
                business_line_uid=str(raw.get("business_line_uid") or ""),
                kylo_posted_at=str(raw.get("kylo_posted_at") or ""),
                kylo_posted_amount_cents=(
                    int(raw["kylo_posted_amount_cents"])
                    if raw.get("kylo_posted_amount_cents") is not None
                    else None
                ),
                last_changed_at=str(raw.get("last_changed_at") or ""),
            )
        except Exception:
            continue
    return out


def save_row_registry(path: Path, registry: Dict[str, RowRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v.to_dict() for k, v in registry.items()}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


__all__ = [
    "load_row_registry",
    "save_row_registry",
    "save_tick_snapshot",
]
