"""In-Transit drift detection for dual-pool liquidity.

An in-transit transfer leg represents money that left one pool (cash or bank)
and is expected to arrive in the other. When the matching leg never posts, the
float sits in ``BALANCE!K`` indefinitely. This module flags legs that have been
un-reconciled for longer than a threshold (default 7 days) and states which pool
the funds should land in, so an operator can chase the gap.

Pure logic only (no Sheets / SMTP I/O). Consumes the unmatched
``TransferLeg`` objects produced by ``services.posting.transfer_matcher``.

Expected-pool contract (see docs/OWNER_QA_CASH_VS_BANK.md):
  - TO BANK  (cash_out)  -> DEPOSIT   : cash left, should land in BANK
  - WITHDRAW (bank_out)  -> FROM BANK : bank left, should land in CASH
  - DEPOSIT  (bank_in)   arrival with no TO BANK  : already in BANK (arrival gap)
  - FROM BANK(cash_in)   arrival with no WITHDRAW : already in CASH (arrival gap)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence, Tuple

DEFAULT_DRIFT_DAYS = 7

# side -> pool the money should be sitting in
_EXPECTED_POOL = {
    "cash_out": "BANK",   # TO BANK bagged from cash, awaiting bank DEPOSIT
    "bank_out": "CASH",   # bank WITHDRAW, awaiting cash FROM BANK
    "cash_in": "CASH",    # FROM BANK arrived in cash without a WITHDRAW
    "bank_in": "BANK",    # DEPOSIT arrived in bank without a TO BANK
}

# out-side legs are money genuinely still in transit; in-side legs are arrivals
# that lack a recorded departure (a bookkeeping gap, funds already present).
_IN_TRANSIT_SIDES = {"cash_out", "bank_out"}


@dataclass
class DriftingTransfer:
    uid: str
    family: str          # to_bank | from_bank
    side: str            # cash_out | bank_out | cash_in | bank_in
    amount: float        # absolute dollars
    since_date: date
    age_days: int
    expected_pool: str   # "BANK" | "CASH"
    kind: str            # "in_transit" | "arrival_gap"
    description: str = ""


def expected_pool_for(side: str) -> Optional[str]:
    return _EXPECTED_POOL.get(side)


def _kind_for(side: str) -> str:
    return "in_transit" if side in _IN_TRANSIT_SIDES else "arrival_gap"


def find_drifting_transfers(
    unmatched_legs: Iterable,
    as_of: date,
    *,
    drift_days: int = DEFAULT_DRIFT_DAYS,
    include_arrival_gaps: bool = False,
) -> List[DriftingTransfer]:
    """Return unmatched transfer legs older than ``drift_days`` as of ``as_of``.

    ATM legs are ignored (ATM LOAD/SWITCH are not a $-for-$ transit pair).
    By default only true in-transit (out-side) legs are returned; set
    ``include_arrival_gaps=True`` to also surface unmatched arrivals.
    """
    out: List[DriftingTransfer] = []
    for leg in unmatched_legs:
        family = getattr(leg, "family", "")
        if family not in ("to_bank", "from_bank"):
            continue
        side = getattr(leg, "side", "")
        since = getattr(leg, "d", None)
        if not isinstance(since, date):
            continue
        age = (as_of - since).days
        if age <= drift_days:
            continue
        kind = _kind_for(side)
        if kind == "arrival_gap" and not include_arrival_gaps:
            continue
        pool = expected_pool_for(side)
        if pool is None:
            continue
        out.append(
            DriftingTransfer(
                uid=str(getattr(leg, "uid", "") or f"{family}|{side}|{since.isoformat()}"),
                family=family,
                side=side,
                amount=round(float(getattr(leg, "amount", 0.0) or 0.0), 2),
                since_date=since,
                age_days=age,
                expected_pool=pool,
                kind=kind,
                description=str(getattr(leg, "description", "") or ""),
            )
        )
    # Oldest and largest first.
    out.sort(key=lambda x: (-x.age_days, -x.amount))
    return out


def drift_totals_by_pool(drifts: Sequence[DriftingTransfer]) -> dict:
    """Sum drifting amounts by the pool they should land in."""
    totals = {"BANK": 0.0, "CASH": 0.0}
    for d in drifts:
        totals[d.expected_pool] = round(totals.get(d.expected_pool, 0.0) + d.amount, 2)
    return totals


def format_drift_email(
    drifts: Sequence[DriftingTransfer],
    as_of: date,
    *,
    drift_days: int = DEFAULT_DRIFT_DAYS,
) -> Tuple[str, str]:
    """Build (subject, body) for the drift alert email."""
    total = round(sum(d.amount for d in drifts), 2)
    by_pool = drift_totals_by_pool(drifts)
    subject = (
        f"[Kylo] In-Transit drift: ${total:,.2f} across "
        f"{len(drifts)} transfer(s) > {drift_days} days"
    )
    lines: List[str] = []
    lines.append(
        f"As of {as_of.isoformat()}, the following transfers have been in transit "
        f"for more than {drift_days} days and have not reconciled:"
    )
    lines.append("")
    for d in drifts:
        label = d.description or d.side
        lines.append(
            f"  - ${d.amount:,.2f}  should be in {d.expected_pool}  "
            f"(left on {d.since_date.isoformat()}, {d.age_days} days ago; {label})"
        )
    lines.append("")
    lines.append(
        f"Totals expected to land -> BANK: ${by_pool.get('BANK', 0.0):,.2f}, "
        f"CASH: ${by_pool.get('CASH', 0.0):,.2f}."
    )
    lines.append("")
    lines.append(
        "These amounts are currently sitting in BALANCE In Transit (column K). "
        "Confirm the matching bank/cash leg posted, or correct the entry."
    )
    return subject, "\n".join(lines)


def drift_dedupe_key(d: DriftingTransfer) -> str:
    """Stable key for suppressing repeat alerts for the same drift."""
    return d.uid


__all__ = [
    "DEFAULT_DRIFT_DAYS",
    "DriftingTransfer",
    "expected_pool_for",
    "find_drifting_transfers",
    "drift_totals_by_pool",
    "format_drift_email",
    "drift_dedupe_key",
]
