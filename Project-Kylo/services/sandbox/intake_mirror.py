"""Live → sandbox intake mirror (TRANSACTIONS + BANK only).

One-way: LIVE 2026 workbook → KYLO 2026 SANDBOX. Never writes back to live.
Used by the 120s sandbox mirror daemon so BALANCE EOD can track day-to-day
while sandbox layout / rules are improved in isolation.

Full intake rows are copied — including Processed/Approved/NOTES/log columns —
so sandbox TRANSACTIONS gets live TRANSACTIONS notes and sandbox BANK gets live
BANK notes (respectively). Values only; other sandbox tabs are untouched.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Defaults match KYLO_2026 live + KYLO_2026_SANDBOX instance config.
DEFAULT_LIVE_SID = "1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE"
DEFAULT_SANDBOX_SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
DEFAULT_SA_JSON = r"E:/secrets/gcp/sa.json"
INTAKE_TABS = ("TRANSACTIONS", "BANK")
# Wide enough for date/company/source/amount + Processed/Approved/NOTES/log cols.
COPY_RANGE = "A1:Z5000"
# Fingerprint covers the full mirrored width so note/log edits also trigger sync.
FP_RANGE = "A2:Z5000"


def _a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_sheets_service(sa_json: str, *, readonly: bool = False):
    scopes = (
        ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        if readonly
        else ["https://www.googleapis.com/auth/spreadsheets"]
    )
    creds = service_account.Credentials.from_service_account_file(sa_json, scopes=scopes)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _retry(fn, *, attempts: int = 5, base_sleep: float = 1.5):
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except HttpError as exc:
            last = exc
            status = getattr(exc.resp, "status", None)
            if status not in (429, 500, 503) or i == attempts - 1:
                raise
            time.sleep(base_sleep * (2**i))
        except Exception as exc:  # pragma: no cover - network
            last = exc
            if i == attempts - 1:
                raise
            time.sleep(base_sleep * (2**i))
    raise last  # type: ignore[misc]


def _get_values(svc, sid: str, rng: str, *, formatted: bool = False) -> list[list[Any]]:
    opt = "FORMATTED_VALUE" if formatted else "UNFORMATTED_VALUE"
    return (
        _retry(
            lambda: svc.spreadsheets()
            .values()
            .get(spreadsheetId=sid, range=rng, valueRenderOption=opt)
            .execute()
        ).get("values", [])
        or []
    )


def _clear(svc, sid: str, rng: str) -> None:
    _retry(
        lambda: svc.spreadsheets()
        .values()
        .clear(spreadsheetId=sid, range=rng)
        .execute()
    )


def _update(svc, sid: str, rng: str, values: list[list[Any]]) -> None:
    _retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=sid,
            range=rng,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


@dataclass
class IntakeFingerprint:
    """Cheap change detector for live intake (row counts + content hash)."""

    tab_hashes: dict[str, str]
    tab_rows: dict[str, int]
    digest: str

    @classmethod
    def from_tabs(cls, tab_payloads: dict[str, list[list[Any]]]) -> "IntakeFingerprint":
        tab_hashes: dict[str, str] = {}
        tab_rows: dict[str, int] = {}
        parts: list[str] = []
        for tab in INTAKE_TABS:
            rows = tab_payloads.get(tab) or []
            # Normalize: stringify cells so float/int/str compare stably.
            # Includes NOTES/log columns so posting-note changes also sync.
            norm = "\n".join("|".join("" if c is None else str(c) for c in r) for r in rows)
            h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]
            nonempty = sum(1 for r in rows if r and str(r[0]).strip())
            tab_hashes[tab] = h
            tab_rows[tab] = nonempty
            parts.append(f"{tab}:{nonempty}:{h}")
        digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]
        return cls(tab_hashes=tab_hashes, tab_rows=tab_rows, digest=digest)


@dataclass
class SyncResult:
    changed: bool
    fingerprint: IntakeFingerprint
    previous_digest: str | None
    tabs_copied: list[str]
    rows_written: dict[str, int]
    elapsed_seconds: float
    error: str | None = None


def fingerprint_live(
    svc,
    live_sid: str,
    *,
    tabs: Sequence[str] = INTAKE_TABS,
) -> IntakeFingerprint:
    payloads: dict[str, list[list[Any]]] = {}
    for tab in tabs:
        payloads[tab] = _get_values(svc, live_sid, _a1(tab, FP_RANGE), formatted=False)
    return IntakeFingerprint.from_tabs(payloads)


def sync_intake_live_to_sandbox(
    *,
    sa_json: str = DEFAULT_SA_JSON,
    live_sid: str = DEFAULT_LIVE_SID,
    sandbox_sid: str = DEFAULT_SANDBOX_SID,
    tabs: Sequence[str] = INTAKE_TABS,
    force: bool = False,
    previous_digest: str | None = None,
) -> SyncResult:
    """Copy TRANSACTIONS/BANK from live → sandbox when the live fingerprint changes.

    Full rows including Processed/Approved/NOTES/log columns are written to the
    matching sandbox tab (TRANSACTIONS→TRANSACTIONS, BANK→BANK). Never writes live.

    Returns a SyncResult. ``changed=False`` means no write was needed.
    """
    t0 = time.monotonic()
    ro = build_sheets_service(sa_json, readonly=True)
    fp = fingerprint_live(ro, live_sid, tabs=tabs)
    if not force and previous_digest and previous_digest == fp.digest:
        return SyncResult(
            changed=False,
            fingerprint=fp,
            previous_digest=previous_digest,
            tabs_copied=[],
            rows_written={},
            elapsed_seconds=round(time.monotonic() - t0, 2),
        )

    rw = build_sheets_service(sa_json, readonly=False)
    rows_written: dict[str, int] = {}
    copied: list[str] = []
    try:
        for tab in tabs:
            # FORMATTED_VALUE preserves human-readable NOTES / Posted log text.
            vals = _get_values(ro, live_sid, _a1(tab, COPY_RANGE), formatted=True)
            _clear(rw, sandbox_sid, _a1(tab, COPY_RANGE))
            if vals:
                _update(rw, sandbox_sid, _a1(tab, "A1"), vals)
            rows_written[tab] = len(vals)
            copied.append(tab)
            time.sleep(0.4)  # mild pacing between tabs
    except Exception as exc:
        return SyncResult(
            changed=False,
            fingerprint=fp,
            previous_digest=previous_digest,
            tabs_copied=copied,
            rows_written=rows_written,
            elapsed_seconds=round(time.monotonic() - t0, 2),
            error=str(exc),
        )

    return SyncResult(
        changed=True,
        fingerprint=fp,
        previous_digest=previous_digest,
        tabs_copied=copied,
        rows_written=rows_written,
        elapsed_seconds=round(time.monotonic() - t0, 2),
    )


def write_heartbeat(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["checked_at"] = _now_iso()
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def load_last_digest(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return str(data.get("digest") or "") or None
    except Exception:
        return None


__all__ = [
    "DEFAULT_LIVE_SID",
    "DEFAULT_SANDBOX_SID",
    "DEFAULT_SA_JSON",
    "INTAKE_TABS",
    "IntakeFingerprint",
    "SyncResult",
    "fingerprint_live",
    "sync_intake_live_to_sandbox",
    "write_heartbeat",
    "load_last_digest",
    "build_sheets_service",
]
