from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def make_row_key(source_spreadsheet_id: str, source_tab: str, row_index_0based: int) -> str:
    sid = str(source_spreadsheet_id or "").strip()
    tab = str(source_tab or "TRANSACTIONS").strip().upper()
    return f"{sid}|{tab}|{int(row_index_0based)}"


def make_business_line_uid(
    source_spreadsheet_id: str,
    source_tab: str,
    company_id: str,
    posted_date: str,
    description: str,
) -> str:
    """Stable transaction identity (no row index, no amount) — survives row inserts."""
    sid = str(source_spreadsheet_id or "").strip()
    tab = str(source_tab or "TRANSACTIONS").strip().upper()
    company = str(company_id or "").strip().upper()
    desc = re.sub(r"\s+", " ", str(description or "").strip()).upper()
    date = str(posted_date or "").strip()
    return f"{sid}|{tab}|{company}|{date}|{desc}"


def sheet_row_1based(row_index_0based: int) -> int:
    return int(row_index_0based) + 1


def content_fingerprint(
    posted_date: str,
    company_id: str,
    description: str,
    amount_cents: int,
) -> str:
    desc = re.sub(r"\s+", " ", str(description or "").strip())
    return f"{posted_date}|{(company_id or '').strip().upper()}|{int(amount_cents)}|{desc}"


@dataclass
class RowRecord:
    row_key: str
    source_spreadsheet_id: str
    source_tab: str
    row_index_0based: int
    company_id: str = ""
    posted_date: str = ""
    description: str = ""
    amount_cents: int = 0
    posted_flag: bool = False
    first_seen_at: str = ""
    content_fp: str = ""
    txn_uid: str = ""
    business_line_uid: str = ""
    kylo_posted_at: str = ""
    kylo_posted_amount_cents: Optional[int] = None
    last_changed_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_txn(cls, txn: Dict[str, Any], *, first_seen_at: str = "") -> Optional["RowRecord"]:
        sid = str(txn.get("source_spreadsheet_id") or "").strip()
        tab = str(txn.get("source_tab") or "TRANSACTIONS").strip()
        if not sid:
            return None
        try:
            row0 = int(txn.get("row_index_0based") or 0)
        except Exception:
            row0 = 0
        company = str(txn.get("company_id") or "").strip().upper()
        posted_date = str(txn.get("posted_date") or "").strip()
        description = str(txn.get("description") or "")
        try:
            amount_cents = int(txn.get("amount_cents") or 0)
        except Exception:
            amount_cents = 0
        posted_flag = bool(txn.get("posted_flag"))
        rk = make_row_key(sid, tab, row0)
        fp = content_fingerprint(posted_date, company, description, amount_cents)
        bl_uid = str(txn.get("business_line_uid") or "").strip() or make_business_line_uid(
            sid, tab, company, posted_date, description
        )
        txn_uid = str(txn.get("txn_uid") or "").strip()
        return cls(
            row_key=rk,
            source_spreadsheet_id=sid,
            source_tab=tab,
            row_index_0based=row0,
            company_id=company,
            posted_date=posted_date,
            description=description,
            amount_cents=amount_cents,
            posted_flag=posted_flag,
            first_seen_at=first_seen_at,
            content_fp=fp,
            txn_uid=txn_uid,
            business_line_uid=bl_uid,
        )


@dataclass
class ChangeEvent:
    ts: str
    event: str
    row_key: str
    source_spreadsheet_id: str
    source_tab: str
    sheet_row: int
    company_id: str = ""
    changed_field: str = ""
    before: str = ""
    after: str = ""
    anomalies: List[str] = field(default_factory=list)
    posted_date: str = ""
    description: str = ""
    amount_cents: int = 0
    txn_uid: str = ""
    business_line_uid: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def human_line(self, instance_id: str = "") -> str:
        parts = [
            self.ts,
            instance_id or "-",
            self.company_id or "-",
            self.source_spreadsheet_id[:12] + "..." if len(self.source_spreadsheet_id) > 12 else self.source_spreadsheet_id,
            self.source_tab,
            f"row {self.sheet_row}",
            self.event,
        ]
        if self.business_line_uid:
            parts.append(f"bl={self.business_line_uid[-40:]}")
        if self.changed_field:
            parts.append(self.changed_field)
        if self.before or self.after:
            parts.append(f"{self.before} -> {self.after}")
        elif self.description:
            parts.append(self.description[:60])
        if self.anomalies:
            parts.append(f"ANOMALY={','.join(self.anomalies)}")
        return " | ".join(str(p) for p in parts)


__all__ = [
    "ChangeEvent",
    "RowRecord",
    "content_fingerprint",
    "make_business_line_uid",
    "make_row_key",
    "sheet_row_1based",
]
