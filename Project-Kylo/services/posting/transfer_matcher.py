"""
Transfer / In-Transit matcher for dual-pool liquidity.

Owner contract (OWNER_QA_CASH_VS_BANK):
- TO BANK (cash) ↔ DEPOSIT (bank): cash→bank; lag sits in In Transit
- FROM BANK (cash) ↔ WITHDRAW (bank): bank→cash; lag sits in In Transit
- ATM LOAD (cash) ↔ SWITCH (bank): ATM float lag sits in In Transit
  (ATM LOAD/SWITCH already move Cash/Bank EOD via JGD helpers — only K moves here)

Transfers must not change AVAILABLE = Bank + Cash + InTransit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


def _parse_date(v) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except Exception:
            continue
    return None


def _norm(s: str) -> str:
    return " ".join(str(s or "").strip().upper().split())


def _abs_amt(cents: Optional[int], amount=None) -> float:
    if cents is not None:
        return abs(float(cents) / 100.0)
    try:
        return abs(float(amount or 0))
    except Exception:
        return 0.0


@dataclass
class TransferLeg:
    side: str  # cash_out | bank_in | cash_in | bank_out | atm_out | atm_in
    family: str  # to_bank | from_bank | atm
    d: date
    amount: float  # always abs
    uid: str
    description: str = ""
    matched: bool = False


@dataclass
class TransferMatch:
    family: str
    amount: float
    cash_date: date
    bank_date: date
    cash_uid: str
    bank_uid: str


@dataclass
class DayTransferNets:
    """Per-day adjustments for BALANCE wiring."""

    # Pot moves for TO/FROM BANK (ATM already in JGD helpers — excluded here)
    cash: float = 0.0
    bank: float = 0.0
    # In-transit day delta (all families)
    in_transit: float = 0.0


@dataclass
class TransferMatchResult:
    matches: List[TransferMatch] = field(default_factory=list)
    unmatched: List[TransferLeg] = field(default_factory=list)
    by_date: Dict[date, DayTransferNets] = field(default_factory=dict)


def _ensure_day(by_date: Dict[date, DayTransferNets], d: date) -> DayTransferNets:
    if d not in by_date:
        by_date[d] = DayTransferNets()
    return by_date[d]


def classify_transfer_leg(
    *,
    source_tab: str,
    description: str,
    amount_cents: Optional[int] = None,
    amount=None,
    posted_date=None,
    txn_uid: str = "",
) -> Optional[TransferLeg]:
    """Map an intake row to a transfer leg, or None if not a transfer."""
    tab = _norm(source_tab)
    desc = _norm(description)
    d = _parse_date(posted_date)
    amt = _abs_amt(amount_cents, amount)
    if d is None or amt < 0.005:
        return None
    uid = txn_uid or f"{tab}|{d.isoformat()}|{desc}|{amt:.2f}"

    if tab == "TRANSACTIONS":
        if desc == "TO BANK" or desc.startswith("TO BANK "):
            return TransferLeg("cash_out", "to_bank", d, amt, uid, desc)
        if desc in ("FROM BANK", "ATM WITHDRAW") or desc.startswith("FROM BANK"):
            return TransferLeg("cash_in", "from_bank", d, amt, uid, desc)
        if desc == "ATM LOAD" or desc.startswith("ATM LOAD"):
            return TransferLeg("atm_out", "atm", d, amt, uid, desc)
        return None

    if tab == "BANK":
        if desc == "DEPOSIT" or desc.startswith("DEPOSIT "):
            return TransferLeg("bank_in", "to_bank", d, amt, uid, desc)
        if desc == "WITHDRAW" or desc.startswith("WITHDRAW"):
            return TransferLeg("bank_out", "from_bank", d, amt, uid, desc)
        if desc == "SWITCH" or desc.startswith("SWITCH"):
            return TransferLeg("atm_in", "atm", d, amt, uid, desc)
        return None

    return None


def _match_family(
    outs: List[TransferLeg],
    inns: List[TransferLeg],
    *,
    window_days: int,
    amount_tolerance: float,
    family: str,
) -> Tuple[List[TransferMatch], List[TransferLeg], List[TransferLeg]]:
    """Greedy match outs→inns by closest date within window, amount within tol."""
    matches: List[TransferMatch] = []
    outs_sorted = sorted(outs, key=lambda x: (x.d, x.amount, x.uid))
    inns_avail = sorted(inns, key=lambda x: (x.d, x.amount, x.uid))

    for out in outs_sorted:
        best_i = None
        best_score = None
        for i, inn in enumerate(inns_avail):
            if inn.matched:
                continue
            if abs(inn.amount - out.amount) > amount_tolerance:
                continue
            lag = abs((inn.d - out.d).days)
            if lag > window_days:
                continue
            # Prefer same day, then nearer date
            score = (lag, abs(inn.amount - out.amount))
            if best_score is None or score < best_score:
                best_score = score
                best_i = i
        if best_i is None:
            continue
        inn = inns_avail[best_i]
        out.matched = True
        inn.matched = True
        # cash_date / bank_date by family
        if family == "to_bank":
            cash_date, bank_date = out.d, inn.d
            cash_uid, bank_uid = out.uid, inn.uid
        elif family == "from_bank":
            # out = cash_in, inn = bank_out — rename
            cash_date, bank_date = out.d, inn.d
            cash_uid, bank_uid = out.uid, inn.uid
        else:  # atm
            cash_date, bank_date = out.d, inn.d
            cash_uid, bank_uid = out.uid, inn.uid
        matches.append(
            TransferMatch(
                family=family,
                amount=out.amount,
                cash_date=cash_date,
                bank_date=bank_date,
                cash_uid=cash_uid,
                bank_uid=bank_uid,
            )
        )

    unmatched = [x for x in outs_sorted + inns_avail if not x.matched]
    return matches, unmatched, []


def match_transfers(
    legs: Sequence[TransferLeg],
    *,
    window_days: int = 3,
    amount_tolerance: float = 0.02,
) -> TransferMatchResult:
    """
    Match transfer legs and produce per-day cash/bank/in-transit nets.

    Accounting (Available constant):
      to_bank cash_out day:  cash -= A;  K += A
      to_bank bank_in day:   bank += A;  K -= A
      from_bank cash_in day: cash += A;  K -= A
      from_bank bank_out day: bank -= A; K += A
      atm out day:           K += A   (cash already via JGD)
      atm in day:            K -= A   (bank already via JGD)

    Unmatched legs get the same day treatment as if the other side hasn't posted yet.
    """
    by_family: Dict[str, Dict[str, List[TransferLeg]]] = {
        "to_bank": {"cash_out": [], "bank_in": []},
        "from_bank": {"cash_in": [], "bank_out": []},
        "atm": {"atm_out": [], "atm_in": []},
    }
    for leg in legs:
        bucket = by_family.get(leg.family)
        if bucket is not None and leg.side in bucket:
            bucket[leg.side].append(leg)

    result = TransferMatchResult()

    # to_bank: cash_out ↔ bank_in
    m, _, _ = _match_family(
        by_family["to_bank"]["cash_out"],
        by_family["to_bank"]["bank_in"],
        window_days=window_days,
        amount_tolerance=amount_tolerance,
        family="to_bank",
    )
    result.matches.extend(m)

    # from_bank: cash_in ↔ bank_out
    m, _, _ = _match_family(
        by_family["from_bank"]["cash_in"],
        by_family["from_bank"]["bank_out"],
        window_days=window_days,
        amount_tolerance=amount_tolerance,
        family="from_bank",
    )
    result.matches.extend(m)

    # atm: atm_out ↔ atm_in
    m, _, _ = _match_family(
        by_family["atm"]["atm_out"],
        by_family["atm"]["atm_in"],
        window_days=window_days,
        amount_tolerance=amount_tolerance,
        family="atm",
    )
    result.matches.extend(m)

    result.unmatched = [leg for leg in legs if not leg.matched]

    # Apply matched pairs
    for m in result.matches:
        if m.family == "to_bank":
            _ensure_day(result.by_date, m.cash_date).cash -= m.amount
            _ensure_day(result.by_date, m.cash_date).in_transit += m.amount
            _ensure_day(result.by_date, m.bank_date).bank += m.amount
            _ensure_day(result.by_date, m.bank_date).in_transit -= m.amount
        elif m.family == "from_bank":
            _ensure_day(result.by_date, m.cash_date).cash += m.amount
            _ensure_day(result.by_date, m.cash_date).in_transit -= m.amount
            _ensure_day(result.by_date, m.bank_date).bank -= m.amount
            _ensure_day(result.by_date, m.bank_date).in_transit += m.amount
        else:  # atm — pots already moved via JGD
            _ensure_day(result.by_date, m.cash_date).in_transit += m.amount
            _ensure_day(result.by_date, m.bank_date).in_transit -= m.amount

    # Unmatched: one-sided, sit in / leave transit
    for leg in result.unmatched:
        day = _ensure_day(result.by_date, leg.d)
        if leg.side == "cash_out":  # TO BANK waiting deposit
            day.cash -= leg.amount
            day.in_transit += leg.amount
        elif leg.side == "bank_in":  # DEPOSIT without TO BANK
            day.bank += leg.amount
            day.in_transit -= leg.amount
        elif leg.side == "cash_in":  # FROM BANK waiting withdraw
            day.cash += leg.amount
            day.in_transit -= leg.amount
        elif leg.side == "bank_out":  # WITHDRAW waiting FROM BANK
            day.bank -= leg.amount
            day.in_transit += leg.amount
        elif leg.side == "atm_out":
            day.in_transit += leg.amount
        elif leg.side == "atm_in":
            day.in_transit -= leg.amount

    return result


def legs_from_intake_rows(rows: Iterable[dict]) -> List[TransferLeg]:
    out: List[TransferLeg] = []
    for t in rows:
        leg = classify_transfer_leg(
            source_tab=str(t.get("source_tab") or ""),
            description=str(t.get("description") or t.get("source") or ""),
            amount_cents=t.get("amount_cents"),
            amount=t.get("amount"),
            posted_date=t.get("posted_date"),
            txn_uid=str(t.get("txn_uid") or ""),
        )
        if leg:
            out.append(leg)
    return out


def running_in_transit(by_date: Dict[date, DayTransferNets], dates: Sequence[date]) -> Dict[date, float]:
    """Cumulative K from day deltas along an ordered date spine."""
    run = 0.0
    out: Dict[date, float] = {}
    for d in dates:
        nets = by_date.get(d) or DayTransferNets()
        run = round(run + nets.in_transit, 2)
        out[d] = run
    return out
