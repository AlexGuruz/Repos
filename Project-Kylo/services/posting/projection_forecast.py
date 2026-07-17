"""Forward liquidity projection for the dual-pool BALANCE.

Actual region (date <= boundary ``D0``) uses the raw account ledgers
(TRANSACTIONS / BANK). Beyond ``D0`` the daily cash/bank pool nets come from the
manual forecast cells already in the target category tabs, per
``docs/DUAL_POOL_TARGET_MODEL.md``. This module holds:

  * the pool -> (target tab, column) map,
  * a live ``SUMIF`` formula builder (so the sheet updates as projections are
    typed), and
  * a pure running-EOD projector (``project_forward_eod``) used by tests and by
    any non-sheet caller.

INCOME transfer nets (cols AB/AC) are intentionally excluded so transfers never
change Available.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

# pool -> [(target tab, signed daily column)]
CASH_NET_TARGETS: List[Tuple[str, str]] = [
    ("CASH EXPENSES", "B"),
    ("PAYROLL", "V"),        # Payroll Cash Net
    ("JGD", "K"),            # JGD Cash Net
    ("NUGZ COG", "B"),
    ("CANNABIS DIST", "B"),
    ("NON CANNABIS", "B"),
    ("ALLOCATED", "B"),
    ("INCOME", "X"),         # Income Cash Net (transfers excluded)
]
BANK_NET_TARGETS: List[Tuple[str, str]] = [
    ("BANK EXPENSES", "B"),
    ("PAYROLL", "W"),        # Payroll Bank Net
    ("JGD", "L"),            # JGD Bank Net
    ("CC Payments", "B"),
    ("INCOME", "Y"),         # Income Bank Net (transfers excluded)
]


def quote_tab(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'" if " " in tab else tab


def net_sumif_formula(targets: Sequence[Tuple[str, str]], date_cell: str) -> str:
    """Live formula: sum each target's signed daily column for the row's date.

    ``date_cell`` is the A1 reference holding the date (e.g. ``$B23``).
    """
    terms = [
        f"IFERROR(SUMIF({quote_tab(tab)}!$A:$A,{date_cell},{quote_tab(tab)}!${col}:${col}),0)"
        for tab, col in targets
    ]
    return "=" + "+".join(terms)


@dataclass
class ForwardEOD:
    dates: List[date] = field(default_factory=list)
    bank: List[float] = field(default_factory=list)
    cash: List[float] = field(default_factory=list)
    in_transit: List[float] = field(default_factory=list)
    available: List[float] = field(default_factory=list)


def project_forward_eod(
    *,
    boundary_bank: float,
    boundary_cash: float,
    dates: Sequence[date],
    cash_net: Dict[date, float],
    bank_net: Dict[date, float],
    in_transit: Optional[Dict[date, float]] = None,
) -> ForwardEOD:
    """Continue the running EOD past the boundary with projected day nets.

    ``dates`` must be the strictly-future spine (all > D0), in order.
    ``boundary_bank`` / ``boundary_cash`` are the actual EOD values on D0.
    Returns per-day Bank/Cash/InTransit/Available. Available = Bank+Cash+K, so it
    visibly declines (and can go negative) when projected expenses outrun income.
    """
    in_transit = in_transit or {}
    out = ForwardEOD()
    run_bank = float(boundary_bank)
    run_cash = float(boundary_cash)
    last_k = 0.0
    for d in dates:
        run_bank = round(run_bank + float(bank_net.get(d, 0.0)), 2)
        run_cash = round(run_cash + float(cash_net.get(d, 0.0)), 2)
        if d in in_transit:
            last_k = float(in_transit[d])
        k = round(last_k, 2)
        out.dates.append(d)
        out.bank.append(run_bank)
        out.cash.append(run_cash)
        out.in_transit.append(k)
        out.available.append(round(run_bank + run_cash + k, 2))
    return out


__all__ = [
    "CASH_NET_TARGETS",
    "BANK_NET_TARGETS",
    "quote_tab",
    "net_sumif_formula",
    "ForwardEOD",
    "project_forward_eod",
]
