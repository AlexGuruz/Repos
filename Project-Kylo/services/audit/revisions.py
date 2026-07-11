from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.audit.row_model import ChangeEvent
from services.common.retry import google_api_execute


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def poll_spreadsheet_revisions(
    *,
    spreadsheet_ids: List[str],
    revision_state_path: Path,
    service=None,
    drive_service=None,
) -> List[ChangeEvent]:
    """Poll Drive revisions API; emit event when revision count increases."""
    if not spreadsheet_ids:
        return []
    state = _load_state(revision_state_path)
    ts = _utc_now_iso()
    events: List[ChangeEvent] = []

    if drive_service is None:
        try:
            import os

            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if not sa_path:
                return []
            creds = Credentials.from_service_account_file(
                sa_path,
                scopes=["https://www.googleapis.com/auth/drive.readonly"],
            )
            drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
        except Exception as e:
            print(f"[AUDIT] WARN: Drive revisions unavailable: {e}")
            return []

    for sid in spreadsheet_ids:
        sid = str(sid).strip()
        if not sid:
            continue
        try:
            resp = google_api_execute(
                drive_service.revisions().list(fileId=sid, pageSize=100, fields="revisions(id,modifiedTime,lastModifyingUser)"),
                label="audit:drive_revisions",
            )
            revisions = resp.get("revisions") or []
            count = len(revisions)
            prev = state.get(sid) or {}
            prev_count = int(prev.get("revision_count") or 0)
            if prev_count and count > prev_count:
                latest = revisions[-1] if revisions else {}
                user = (latest.get("lastModifyingUser") or {}).get("displayName") or "unknown"
                mod = latest.get("modifiedTime") or ts
                events.append(
                    ChangeEvent(
                        ts=ts,
                        event="ANOMALY",
                        row_key=f"{sid}|REVISION",
                        source_spreadsheet_id=sid,
                        source_tab="",
                        sheet_row=0,
                        changed_field="revision",
                        before=str(prev_count),
                        after=str(count),
                        anomalies=["SHEETS_REVISION_DETECTED"],
                        description=f"Drive revision +{count - prev_count} by {user} at {mod}",
                    )
                )
            state[sid] = {
                "revision_count": count,
                "last_checked_at": ts,
                "last_modified": (revisions[-1].get("modifiedTime") if revisions else prev.get("last_modified")),
            }
        except Exception as e:
            print(f"[AUDIT] WARN: revision poll failed for {sid[:12]}: {e}")

    _save_state(revision_state_path, state)
    return events


__all__ = ["poll_spreadsheet_revisions"]
