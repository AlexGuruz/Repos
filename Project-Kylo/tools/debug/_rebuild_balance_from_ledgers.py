"""
Rebuild BALANCE so Cash EOD / Bank EOD are the ACTUAL account ledgers.

Owner truth model:
  Cash EOD (J) = running balance of TRANSACTIONS tab (the physical cash pool ledger)
  Bank EOD (I) = opening bank + running balance of BANK tab (bank statement)
  In Transit (K) = running float of TRUE transfers still mid-flight
                   (TO BANK<->DEPOSIT, FROM BANK<->WITHDRAW timing gaps only)
  AVAILABLE (L) = I + J + K

ATM LOAD (cash into machine) and SWITCH (ATM revenue to bank) are NOT a $-for-$
transfer pair, so they are NOT netted through In Transit — they stay as real
cash-out / bank-in on their respective ledgers.

J/I are live SUMIFS against the TRANSACTIONS / BANK tabs (same sandbox workbook),
so they always match those tabs' running balances by date.

SANDBOX ONLY: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.environ["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"

from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.posting.transfer_matcher import (
    legs_from_intake_rows,
    match_transfers,
    running_in_transit,
)
from services.posting.in_transit_drift import (
    find_drifting_transfers,
    format_drift_email,
    drift_dedupe_key,
    drift_totals_by_pool,
)
from services.posting.projection_forecast import (
    CASH_NET_TARGETS,
    BANK_NET_TARGETS,
    net_sumif_formula,
)
from services.notify import build_email_notifier
from services.state.store import load_state, save_state
from services.sheets.poster import _extract_spreadsheet_id

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
OPENING_BANK = 4845.52
WINDOW_DAYS = 3

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries=12):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status in (429, 503):
                wait = 35 + i * 12
                print(f"  rate-limit sleep {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("retries exhausted")


def a1(tab, rng):
    return "'" + tab.replace("'", "''") + "'!" + rng


def get(rng, render="UNFORMATTED_VALUE"):
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def update(rng, values, raw=False):
    retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW" if raw else "USER_ENTERED",
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
            continue
    return None


# --- date spine from BALANCE ---
dates_raw = get(a1("BALANCE", "B20:B400"))
spine: List[Optional[date]] = [parse_date(r[0] if r else None) for r in dates_raw]
n = len(spine)
print(f"BALANCE days={n}")

# --- transfer legs (TRUE transfers only: drop atm) for In Transit ---
cfg = load_config()
sa_path = cfg.get("google.service_account_json_path")
intake_sid = _extract_spreadsheet_id(
    (cfg.get("year_workbooks") or {}).get("2026", {}).get("intake_workbook_url")
)
rows: List[dict] = []
for tab in ("TRANSACTIONS", "BANK"):
    csv = download_petty_cash_csv(intake_sid, sa_path, sheet_name_override=tab)
    proc = PettyCashCSVProcessor(
        csv,
        header_rows=int(cfg.get("intake.csv_processor.header_rows", 19)),
        source_tab=tab,
        source_spreadsheet_id=intake_sid,
    )
    for t in proc.parse_transactions():
        t["source_tab"] = tab
        rows.append(t)

legs = [l for l in legs_from_intake_rows(rows) if l.family in ("to_bank", "from_bank")]
result = match_transfers(legs, window_days=WINDOW_DAYS, amount_tolerance=0.02)
valid_dates = [d for d in spine if d]
k_run = running_in_transit(result.by_date, valid_dates)
print(
    f"transfer legs (to/from bank only)={len(legs)} "
    f"matched={len(result.matches)} unmatched={len(result.unmatched)}"
)

# --- Boundary: last actual day. d<=D0 = actual ledger; d>D0 = projection. ---
_actual_dates = [parse_date(t.get("posted_date")) for t in rows]
_actual_dates = [d for d in _actual_dates if d]
D0 = max(_actual_dates) if _actual_dates else None
print(f"boundary D0 (last actual date) = {D0}")


def batch_update(requests):
    retry(
        lambda: svc.spreadsheets()
        .batchUpdate(spreadsheetId=SID, body={"requests": requests})
        .execute()
    )


def sheet_id(title):
    meta = retry(
        lambda: svc.spreadsheets()
        .get(spreadsheetId=SID, fields="sheets.properties")
        .execute()
    )
    for sh in meta.get("sheets", []):
        if sh["properties"]["title"] == title:
            return sh["properties"]["sheetId"]
    return None


# Projected pool nets pulled live from target tabs (per DUAL_POOL_TARGET_MODEL).
# The pool->column map + formula builder live in services.posting.projection_forecast.
def net_formula(targets, r):
    return net_sumif_formula(targets, f"$B{r}")

# --- Build formulas ---
# ACTUAL region (d <= D0):
#   J = cash ledger: cumulative TRANSACTIONS!D where TRANSACTIONS!A <= this date.
#       START OF YEAR (6673.09) lives in TRANSACTIONS so it seeds the opening.
#   I = OPENING_BANK + cumulative BANK!D where BANK!A <= this date.
# PROJECTION region (d > D0): continue the running EOD with projected pool nets
#   from the target tabs (G = proj cash net, H = proj bank net), so a projected
#   shortfall makes J/I/L visibly decline / go negative.
rows_i: List[List[Any]] = []
rows_j: List[List[Any]] = []
rows_k: List[List[Any]] = []
rows_l: List[List[Any]] = []
rows_g: List[List[Any]] = []
rows_h: List[List[Any]] = []

# K carried across any blank-date rows so In Transit never resets to 0.
k_list: List[float] = []
_last_k = 0.0
for d in spine:
    if d is not None and d in k_run:
        _last_k = k_run[d]
    k_list.append(round(_last_k, 2))

first_proj_i: Optional[int] = None
for i, d in enumerate(spine):
    r = 20 + i
    is_actual = d is not None and (D0 is None or d <= D0)
    if is_actual:
        rows_j.append(
            [f'=IFERROR(SUMIFS(TRANSACTIONS!$D:$D,TRANSACTIONS!$A:$A,"<="&$B{r}),0)']
        )
        rows_i.append(
            [f'={OPENING_BANK}+IFERROR(SUMIFS(BANK!$D:$D,BANK!$A:$A,"<="&$B{r}),0)']
        )
        rows_g.append([""])
        rows_h.append([""])
    else:
        if first_proj_i is None:
            first_proj_i = i
        # Projected day nets (blank date rows contribute 0 and just carry).
        rows_g.append([net_formula(CASH_NET_TARGETS, r) if d is not None else ""])
        rows_h.append([net_formula(BANK_NET_TARGETS, r) if d is not None else ""])
        rows_j.append([f"=J{r-1}+IFERROR(G{r},0)"])
        rows_i.append([f"=I{r-1}+IFERROR(H{r},0)"])
    rows_k.append([k_list[i]])
    rows_l.append([f"=I{r}+J{r}+K{r}"])

print(f"writing I/J/K/L + G/H (first projected row index={first_proj_i}) ...")
update(a1("BALANCE", "J20"), rows_j, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "I20"), rows_i, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "G20"), rows_g, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "H20"), rows_h, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "K20"), rows_k, raw=True)
time.sleep(1.2)
update(a1("BALANCE", "L20"), rows_l, raw=False)
time.sleep(1.2)

# --- Category breakdown cols C-H: keep as informational day nets from ledgers ---
# C = cash day net (TRANSACTIONS), D = bank day net (BANK), leave E-H blank/legacy.
rows_c: List[List[Any]] = []
rows_d: List[List[Any]] = []
for i, d in enumerate(spine):
    r = 20 + i
    if i == 0:
        rows_c.append(["=J20-6673.09"])
        rows_d.append([f"=I20-{OPENING_BANK}"])
    else:
        rows_c.append([f"=J{r}-J{r-1}"])
        rows_d.append([f"=I{r}-I{r-1}"])
update(a1("BALANCE", "C20"), rows_c, raw=False)
time.sleep(1.2)
update(a1("BALANCE", "D20"), rows_d, raw=False)

update(
    a1("BALANCE", "A18:L19"),
    [
        [
            "",
            "",
            "Cash day net (TRANSACTIONS)",
            "Bank day net (BANK)",
            "",
            "",
            "Projected cash net (future only)",
            "Projected bank net (future only)",
            "BANK EOD = ledger (actual) then +proj",
            "CASH EOD = ledger (actual) then +proj",
            "IN TRANSIT (TO/FROM BANK float)",
            "AVAILABLE = I+J+K",
        ],
        [
            "",
            "DATE",
            "Cash dNet",
            "Bank dNet",
            "",
            "",
            "Proj Cash Net",
            "Proj Bank Net",
            "Bank EOD",
            "Cash EOD",
            "In Transit",
            "AVAILABLE",
        ],
    ],
    raw=True,
)

# --- Mark the actual -> projected boundary (shade projected rows + note) ---
if first_proj_i is not None:
    bal_sid = sheet_id("BALANCE")
    if bal_sid is not None:
        start_idx = 19 + first_proj_i  # 0-based grid row of first projected data row
        end_idx = 19 + len(spine)
        proj_date0 = spine[first_proj_i]
        batch_update(
            [
                {
                    "repeatCell": {
                        "range": {
                            "sheetId": bal_sid,
                            "startRowIndex": start_idx,
                            "endRowIndex": end_idx,
                            "startColumnIndex": 0,
                            "endColumnIndex": 12,
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": {
                                    "red": 0.99,
                                    "green": 0.96,
                                    "blue": 0.82,
                                }
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                },
                {
                    "updateCells": {
                        "range": {
                            "sheetId": bal_sid,
                            "startRowIndex": start_idx,
                            "endRowIndex": start_idx + 1,
                            "startColumnIndex": 1,
                            "endColumnIndex": 2,
                        },
                        "rows": [
                            {
                                "values": [
                                    {
                                        "note": (
                                            f"PROJECTED from here. Actuals end at D0={D0}. "
                                            f"Rows below use projected cash/bank nets (cols G/H) "
                                            f"from the target tabs; a shortfall drives Available negative."
                                        )
                                    }
                                ]
                            }
                        ],
                        "fields": "note",
                    }
                },
            ]
        )
        print(f"shaded projected rows from {proj_date0} (grid row {start_idx+1})")

# --- Verify readback against python ledger on a few dates ---
time.sleep(2)
check = get(a1("BALANCE", "B20:L400"))
print("\n date          I(bank)      J(cash)        K        L(avail)")
want = {
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 6, 27),
    date(2026, 7, 15),
    date(2026, 7, 16),
    date(2026, 8, 15),
    date(2026, 12, 31),
}
for r in check:
    d = parse_date(r[0] if r else None)
    if d in want:
        row = list(r) + [""] * 11
        def f(x):
            try:
                return float(x or 0)
            except Exception:
                return 0.0
        I, J, K, L = f(row[7]), f(row[8]), f(row[9]), f(row[10])
        tag = "" if (D0 and d <= D0) else "  <proj>"
        print(f" {d}  {I:11,.2f} {J:11,.2f} {K:9,.2f} {L:11,.2f}{tag}")

# --- In Transit drift: flag > drift_days and email the owner ---
drift_days = int(cfg.get("in_transit.drift_days", 7) or 7)
as_of = D0 or date.today()
drifts = find_drifting_transfers(result.unmatched, as_of, drift_days=drift_days)
print(f"\nin-transit drift > {drift_days}d as of {as_of}: {len(drifts)} leg(s)")
if drifts:
    by_pool = drift_totals_by_pool(drifts)
    for dft in drifts:
        print(
            f"  ${dft.amount:,.2f} -> {dft.expected_pool} "
            f"(since {dft.since_date}, {dft.age_days}d; {dft.description})"
        )
    # On-sheet flag on the In Transit header (K19) + note.
    bal_sid = sheet_id("BALANCE")
    total = round(sum(x.amount for x in drifts), 2)
    flag_note = (
        f"DRIFT: ${total:,.2f} in transit > {drift_days}d as of {as_of}. "
        f"Expected -> BANK ${by_pool.get('BANK',0.0):,.2f}, CASH ${by_pool.get('CASH',0.0):,.2f}."
    )
    update(a1("BALANCE", "K18"), [[f"DRIFT ${total:,.2f} >{drift_days}d (see note)"]], raw=True)
    if bal_sid is not None:
        batch_update(
            [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": bal_sid,
                            "startRowIndex": 18,
                            "endRowIndex": 19,
                            "startColumnIndex": 10,
                            "endColumnIndex": 11,
                        },
                        "rows": [{"values": [{"note": flag_note}]}],
                        "fields": "note",
                    }
                }
            ]
        )
    # Email (deduped via posting state); no-op if SMTP not configured.
    try:
        state = load_state()
    except Exception as exc:
        print(f"[DRIFT] state load failed: {exc}; skipping dedupe")
        state = None
    new_drifts = []
    if state is not None:
        active_keys = [drift_dedupe_key(x) for x in drifts]
        state.prune_drift_alerts(active_keys)
        new_drifts = [x for x in drifts if not state.last_drift_alert(drift_dedupe_key(x))]
    else:
        new_drifts = drifts
    if new_drifts:
        notifier = build_email_notifier(cfg, extra_recipients=["alexstonedz@stonedprojects.com"])
        subject, body = format_drift_email(new_drifts, as_of, drift_days=drift_days)
        sent = notifier.send(subject, body)
        if sent:
            print(f"[DRIFT] emailed {len(new_drifts)} new drift(s) to {notifier.recipients}")
            if state is not None:
                now_iso = datetime.now().isoformat(timespec="seconds")
                for x in new_drifts:
                    state.record_drift_alert(drift_dedupe_key(x), now_iso)
        elif not notifier.enabled:
            print(
                f"[DRIFT] email not sent (not configured: missing {notifier.missing()}); "
                f"flagged on sheet only"
            )
        else:
            print(
                "[DRIFT] email send FAILED (see error above); flagged on sheet only. "
                "Not recording dedupe so it retries next run."
            )
    if state is not None:
        try:
            save_state(state)
        except Exception as exc:
            print(f"[DRIFT] state save failed: {exc}")
else:
    # Clear any stale on-sheet drift flag when nothing is drifting.
    update(a1("BALANCE", "K18"), [[""]], raw=True)

print("\nDONE rebuild BALANCE from ledgers")
