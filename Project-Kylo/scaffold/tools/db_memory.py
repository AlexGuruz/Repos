from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

import uuid
from datetime import datetime, timezone


@dataclass
class _Ruleset:
    id: str
    company_id: str
    version: int
    state: str  # 'active' | 'retired'
    effective_at: datetime
    created_at: datetime


@dataclass
class _Rule:
    id: str
    ruleset_id: str
    date: Optional[str]
    source: str
    company_id: str
    amount_expr: Optional[str]
    target_sheet: str
    target_header: str
    match_notes: Optional[str]
    row_hash: str
    created_at: datetime


class _Tx:
    def __init__(self, db: "InMemoryRulesDB") -> None:
        self.db = db

    def __enter__(self) -> "_Tx":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # No-op for in-memory, but could add rollback tracking
        return None


class InMemoryRulesDB:
    """Minimal in-memory DB to exercise importer idempotency and projections."""

    def __init__(self) -> None:
        self._rulesets: List[_Ruleset] = []
        self._rules: List[_Rule] = []
        self._audit: List[Dict[str, Any]] = []

    # --- Transactions ---
    def tx(self) -> _Tx:
        return _Tx(self)

    # --- Rulesets ---
    def get_active_version(self, company_id: str, tx: Optional[_Tx] = None) -> Optional[int]:
        versions = [r.version for r in self._rulesets if r.company_id == company_id and r.state == "active"]
        return max(versions) if versions else None

    def insert_ruleset(self, company_id: str, version: int, tx: Optional[_Tx] = None) -> Tuple[str, int]:
        now = datetime.now(timezone.utc)
        rid = str(uuid.uuid4())
        rs = _Ruleset(
            id=rid,
            company_id=company_id,
            version=version,
            state="active",
            effective_at=now,
            created_at=now,
        )
        self._rulesets.append(rs)
        return rid, version

    def retire_previous_ruleset(self, company_id: str, prior_version: int, tx: Optional[_Tx] = None) -> None:
        for r in self._rulesets:
            if r.company_id == company_id and r.version == prior_version and r.state == "active":
                r.state = "retired"

    # --- Rules ---
    def insert_rule(
        self,
        *,
        ruleset_id: str,
        company_id: str,
        date: Optional[str],
        source: str,
        amount_expr: Optional[str],
        target_sheet: str,
        target_header: str,
        match_notes: Optional[str],
        row_hash: str,
        tx: Optional[_Tx] = None,
    ) -> str:
        if self.rule_exists(company_id, source, row_hash):
            raise ValueError("duplicate rule")
        rid = str(uuid.uuid4())
        self._rules.append(
            _Rule(
                id=rid,
                ruleset_id=ruleset_id,
                date=date,
                source=source,
                company_id=company_id,
                amount_expr=amount_expr,
                target_sheet=target_sheet,
                target_header=target_header,
                match_notes=match_notes,
                row_hash=row_hash,
                created_at=datetime.now(timezone.utc),
            )
        )
        return rid

    def rule_exists(self, company_id: str, source: str, row_hash: str) -> bool:
        return any(
            r.company_id == company_id and r.source == source and r.row_hash == row_hash for r in self._rules
        )

    # --- Queries for Active projection ---
    def fetch_active_sources_rows(self, company_id: str) -> List[List[Any]]:
        """Return rows for Active projection: one per unique Source of the latest active ruleset.

        Columns: [Ruleset_Version, Effective_At, Company_ID, Source, Target_Sheet, Target_Header, Match_Notes, Created_At]
        """
        # Determine latest active ruleset
        active: Optional[_Ruleset] = None
        for rs in self._rulesets:
            if rs.company_id == company_id and rs.state == "active":
                if active is None or rs.version > active.version:
                    active = rs
        if active is None:
            return []

        # Collect rules of that ruleset, dedupe by source keeping last inserted
        rules = [r for r in self._rules if r.ruleset_id == active.id]
        by_source: Dict[str, _Rule] = {}
        for r in rules:
            by_source[r.source] = r

        # Sort by source for deterministic output
        rows: List[List[Any]] = []
        for source in sorted(by_source.keys()):
            r = by_source[source]
            rows.append(
                [
                    active.version,
                    active.effective_at.isoformat(),
                    r.company_id,
                    r.source,
                    r.target_sheet,
                    r.target_header,
                    r.match_notes or "",
                    r.created_at.isoformat(),
                ]
            )
        return rows

    # --- Audit ---
    def audit(self, company_id: str, action: str, ruleset_id: Optional[str], summary: Dict[str, Any], tx: Optional[_Tx] = None) -> None:
        self._audit.append(
            {
                "company_id": company_id,
                "action": action,
                "ruleset_id": ruleset_id,
                "summary": summary,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    # --- Testing helpers ---
    def _seed_rule(
        self,
        *,
        company_id: str,
        version: int,
        date: Optional[str],
        source: str,
        amount_expr: Optional[str],
        target_sheet: str,
        target_header: str,
        match_notes: Optional[str],
        row_hash: str,
    ) -> None:
        rs_id, _ = self.insert_ruleset(company_id, version)
        self.insert_rule(
            ruleset_id=rs_id,
            company_id=company_id,
            date=date,
            source=source,
            amount_expr=amount_expr,
            target_sheet=target_sheet,
            target_header=target_header,
            match_notes=match_notes,
            row_hash=row_hash,
        )


