"""Rewrite BALANCE G/H projection SUMIFs (sandbox only) using spine-scoped ranges."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Optional

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

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries=10):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status in (429, 503):
                time.sleep(35 + i * 10)
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


def update(rng, values):
    retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


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


def main() -> None:
    bal_b = get("'BALANCE'!B20:B400")
    bal_g_f = get("'BALANCE'!G20:G400", "FORMULA")
    d0: Optional[date] = None
    first_proj = None
    for i, row in enumerate(bal_b):
        gf = bal_g_f[i][0] if i < len(bal_g_f) and bal_g_f[i] else ""
        if isinstance(gf, str) and gf.startswith("="):
            first_proj = i
            if i > 0:
                d0 = parse_date(bal_b[i - 1][0] if bal_b[i - 1] else None)
            break
    # Prefer last blank-G day as D0 when formulas are broken (#ERROR)
    if d0 is None:
        for i, row in enumerate(bal_b):
            d = parse_date(row[0] if row else None)
            gf = bal_g_f[i][0] if i < len(bal_g_f) and bal_g_f[i] else ""
            if d == date(2026, 7, 17):
                d0 = d
                first_proj = i + 1
                break
    print(f"D0={d0} first_proj_row={20 + (first_proj or 0)}")

    rows_g, rows_h = [], []
    for i, row in enumerate(bal_b):
        r = 20 + i
        d = parse_date(row[0] if row else None)
        is_actual = d is not None and d0 is not None and d <= d0
        if d is None or is_actual:
            rows_g.append([""])
            rows_h.append([""])
        else:
            date_cell = f"$B{r}"
            rows_g.append([net_sumif_formula(CASH_NET_TARGETS, date_cell)])
            rows_h.append([net_sumif_formula(BANK_NET_TARGETS, date_cell)])

    print(f"writing G/H for {len(rows_g)} rows...")
    update("'BALANCE'!G20", rows_g)
    time.sleep(2)
    update("'BALANCE'!H20", rows_h)
    time.sleep(4)

    bal = get("'BALANCE'!B20:L400")
    want = {date(2026, 7, d) for d in range(17, 22)}
    print("\n=== BALANCE after fix 7/17-7/21 ===")
    print(f"{'row':>4} {'date':12} {'G':>12} {'H':>12} {'I':>12} {'J':>12} {'L':>12}")
    for i, row in enumerate(bal):
        d = parse_date(row[0] if row else None)
        if d not in want:
            continue
        r = 20 + i

        def n(idx: int):
            try:
                return float(row[idx])
            except Exception:
                return row[idx] if len(row) > idx else ""

        print(
            f"{r:4} {str(d):12} {n(5):>12} {n(6):>12} {n(7):>12} {n(8):>12} {n(10):>12}"
        )

    gf = get("'BALANCE'!G219", "FORMULA")
    print("\nG219:", (gf[0][0][:140] if gf and gf[0] else None))


if __name__ == "__main__":
    main()
