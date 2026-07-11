from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.audit.row_model import ChangeEvent


def append_audit_log(path: Path, events: List[ChangeEvent], *, instance_id: str = "") -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ev in events:
            f.write(ev.human_line(instance_id) + "\n")


def append_audit_jsonl(path: Path, events: List[ChangeEvent], *, instance_id: str = "") -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for ev in events:
            payload = ev.to_dict()
            if instance_id:
                payload["instance_id"] = instance_id
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_post_event(
    path: Path,
    *,
    instance_id: str,
    txn_uid: str,
    business_line_uid: str,
    source_sid: str,
    source_tab: str,
    sheet_row: int,
    amount_cents: int,
    target_a1: str,
    note: str,
    flagged: bool = False,
) -> None:
    """Record a successful Kylo post write with timestamp."""
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload: Dict[str, Any] = {
        "ts": ts,
        "event": "POSTED_TO_TARGET",
        "instance_id": instance_id,
        "txn_uid": txn_uid,
        "business_line_uid": business_line_uid,
        "source_spreadsheet_id": source_sid,
        "source_tab": source_tab,
        "sheet_row": sheet_row,
        "amount_cents": amount_cents,
        "target_a1": target_a1,
        "note": note,
        "flagged": flagged,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    log_path = path.with_name("audit.log")
    with log_path.open("a", encoding="utf-8") as f:
        flag_tag = " FLAGGED" if flagged else ""
        f.write(
            f"{ts} | {instance_id} | POSTED_TO_TARGET | row {sheet_row} | "
            f"amount={amount_cents/100:.2f} | {target_a1}{flag_tag} | {note}\n"
        )


def write_diff_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


__all__ = ["append_audit_jsonl", "append_audit_log", "append_post_event", "write_diff_json"]
