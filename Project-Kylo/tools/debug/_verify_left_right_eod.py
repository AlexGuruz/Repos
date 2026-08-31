"""Verify left/right layout + BALANCE G/H after sandbox align (SANDBOX ONLY)."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services.posting.projection_forecast import (
    BANK_NET_TARGETS,
    CASH_NET_TARGETS,
    net_sumif_formula,
)

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
OPENING_BANK = 4845.52

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries=12):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) and e.resp.status in (429, 503):
                time.sleep(25 + i * 12)
                continue
            raise
    raise RuntimeError("retries exhausted")


def get(rng, render="UNFORMATTED_VALUE"):
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def a1(tab, rng):
    return "'" + tab.replace("'", "''") + "'!" + rng


def parse_date(v) -> Optional[date]:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def num(v) -> float:
    if v in (None, ""):
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def ledger_sums() -> Tuple[Dict[date, float], Dict[date, float]]:
    tx = get(a1("TRANSACTIONS", "A20:D5000"))
    bk = get(a1("BANK", "A20:D5000"))
    cash_cum: Dict[date, float] = {}
    bank_cum: Dict[date, float] = {}
    run = 0.0
    # build daily nets then cumulative
    cash_day: Dict[date, float] = {}
    for r in tx:
        d = parse_date(r[0] if r else None)
        if not d:
            continue
        amt = num(r[3] if len(r) > 3 else 0)
        cash_day[d] = cash_day.get(d, 0.0) + amt
    bank_day: Dict[date, float] = {}
    for r in bk:
        d = parse_date(r[0] if r else None)
        if not d:
            continue
        amt = num(r[3] if len(r) > 3 else 0)
        bank_day[d] = bank_day.get(d, 0.0) + amt
    all_d = sorted(set(cash_day) | set(bank_day))
    rc = 0.0
    rb = OPENING_BANK
    for d in all_d:
        rc = round(rc + cash_day.get(d, 0.0), 2)
        rb = round(rb + bank_day.get(d, 0.0), 2)
        cash_cum[d] = rc
        bank_cum[d] = rb
    return cash_cum, bank_cum


def sum_targets(targets, d: date, spine_dates: List[Optional[date]], cols: Dict[str, List[Any]]) -> float:
    total = 0.0
    for tab, col in targets:
        series = cols.get(f"{tab}!{col}", [])
        for i, sd in enumerate(spine_dates):
            if sd == d and i < len(series):
                total += num(series[i][0] if series[i] else 0)
    return round(total, 2)


def main():
    print("=== headers (row 18-19) ===")
    for tab in ("PAYROLL", "JGD", "INCOME"):
        r18 = get(a1(tab, "A18:Z18"), "FORMATTED_VALUE")
        r19 = get(a1(tab, "A19:Z19"), "FORMATTED_VALUE")
        print(tab, "18:", r18[0] if r18 else None)
        print(tab, "19:", r19[0] if r19 else None)

    print("\n=== CASH/BANK target map ===")
    print("CASH", CASH_NET_TARGETS)
    print("BANK", BANK_NET_TARGETS)
    print("sample G formula:", net_sumif_formula(CASH_NET_TARGETS, "$B218")[:120], "...")

    bal = get(a1("BALANCE", "B20:L400"))
    spine: List[Optional[date]] = []
    by_date: Dict[date, Tuple[int, List[Any]]] = {}
    for i, r in enumerate(bal):
        d = parse_date(r[0] if r else None)
        spine.append(d)
        if d:
            by_date[d] = (20 + i, pad := (r + [""] * 12)[:12])

    # Load target helper cols for G/H recomputation
    cols: Dict[str, List[Any]] = {}
    for tab, col in CASH_NET_TARGETS + BANK_NET_TARGETS:
        cols[f"{tab}!{col}"] = get(a1(tab, f"{col}20:{col}{19 + len(spine)}"))

    cash_cum, bank_cum = ledger_sums()

    check_days = [
        date(2026, 7, 16),  # recent actual
        date(2026, 7, 17),  # D0
        date(2026, 7, 19),  # xx/19 month-total trap
        date(2026, 7, 20),  # projected (taxes)
        date(2026, 7, 22),  # further projected
    ]
    print("\n=== verification ===")
    for d in check_days:
        if d not in by_date:
            print(d, "MISSING on BALANCE")
            continue
        row, cells = by_date[d]
        # cells: B=0 ... G=5 H=6 I=7 J=8 K=9 L=10  (since we fetched B:L, index0=B)
        g, h, i_b, j_c, k, l = (
            num(cells[5]),
            num(cells[6]),
            num(cells[7]),
            num(cells[8]),
            num(cells[9]),
            num(cells[10]),
        )
        g_exp = sum_targets(CASH_NET_TARGETS, d, spine, cols)
        h_exp = sum_targets(BANK_NET_TARGETS, d, spine, cols)
        print(f"\n{d} (BALANCE row {row})")
        print(f"  sheet G/H/I/J/K/L = {g}, {h}, {i_b}, {j_c}, {k}, {l}")
        print(f"  recomputed G/H from left/right helpers = {g_exp}, {h_exp}")
        if d <= date(2026, 7, 17):
            lc = cash_cum.get(d)
            lb = bank_cum.get(d)
            print(f"  ledger Cash/Bank EOD = {lc}, {lb}")
            if lc is not None:
                print(f"  Cash EOD vs ledger diff = {round(j_c - lc, 4)}")
            if lb is not None:
                print(f"  Bank EOD vs ledger diff = {round(i_b - lb, 4)}")
            print(f"  G/H blank-or-zero on actual? G={g} H={h}")
        else:
            print(f"  G match? {abs(g - g_exp) < 0.02}  H match? {abs(h - h_exp) < 0.02}")
            # Available continuity
            print(f"  L == I+J+K ? {abs(l - (i_b + j_c + k)) < 0.02}")

    # Month-total trap: G/H on 7/19 should equal helper sum for that day only (not inflated)
    d719 = date(2026, 7, 19)
    if d719 in by_date:
        _, cells = by_date[d719]
        g, h = num(cells[5]), num(cells[6])
        # Pull July month rollup row if any on PAYROLL etc — just flag magnitude
        print(f"\n7/19 magnitude check: G={g} H={h} (month totals are typically 5–6 figures)")
        if abs(g) > 50000 or abs(h) > 50000:
            print("  WARN: suspiciously large — possible month-total collision")
        else:
            print("  OK: not month-total sized")


if __name__ == "__main__":
    main()
