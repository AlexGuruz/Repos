"""
Sandbox: collapse over-split CASH*/BANK* twins to locked dual-pool map;
retarget rules; add EOD helper columns; rewrite BALANCE I/J/L.

SANDBOX ONLY — spreadsheet 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r"E:/secrets/gcp/sa.json"
pointer = json.loads(Path(r"E:/Repos/Project-Kylo/config/sandbox_2026_liquidity.json").read_text())
SID = pointer["sandbox_spreadsheet_id"]

OPENING_BANK = 4845.52
OPENING_CASH = 6673.09

RETARGET_MAP: Dict[str, str] = {
    "CASH PAYROLL": "PAYROLL",
    "BANK PAYROLL": "PAYROLL",
    "CASH JGD": "JGD",
    "BANK JGD": "JGD",
    "CASH INCOME": "INCOME",
    "BANK INCOME": "INCOME",
    "CASH NUGZ COG": "NUGZ COG",
    "BANK NUGZ COG": "NUGZ COG",
    "CASH NON CANNABIS": "NON CANNABIS",
    "BANK NON CANNABIS": "NON CANNABIS",
    "CASH ALLOCATED": "ALLOCATED",
    "BANK ALLOCATED": "ALLOCATED",
    "CASH CANNABIS DIST": "CANNABIS DIST",
    "BANK CC Payments": "CC Payments",
}

HIDE_TABS = [
    "CASH PAYROLL",
    "BANK PAYROLL",
    "CASH JGD",
    "BANK JGD",
    "BANK NUGZ COG",
    "CASH INCOME",
    "BANK INCOME",
    "BANK NON CANNABIS",
    "BANK ALLOCATED",
]

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def quote_tab(name: str) -> str:
    if any(c in name for c in " '\t"):
        return "'" + name.replace("'", "''") + "'"
    return name


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _retry_call(fn, label: str = ""):
    for attempt in range(8):
        try:
            time.sleep(0.4)
            return fn()
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status in (429, 500, 503) and attempt < 7:
                wait = 8 + attempt * 5
                print(f"  rate-limit {label}: sleep {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"retry exhausted: {label}")


def meta_tabs() -> Dict[str, int]:
    m = _retry_call(
        lambda: svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute(),
        "meta",
    )
    out = {}
    for s in m.get("sheets", []):
        p = s["properties"]
        out[p["title"]] = p["sheetId"]
    return out


def get_values(rng: str, render: str = "UNFORMATTED_VALUE") -> List[List[Any]]:
    return _retry_call(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", []),
        f"get {rng[:40]}",
    )


def update_values(rng: str, values: List[List[Any]], raw: bool = False) -> None:
    _retry_call(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW" if raw else "USER_ENTERED",
            body={"values": values},
        )
        .execute(),
        f"upd {rng[:40]}",
    )


def clear_values(rng: str) -> None:
    _retry_call(
        lambda: svc.spreadsheets().values().clear(spreadsheetId=SID, range=rng).execute(),
        f"clr {rng[:40]}",
    )


def batch_update(requests: List[dict]) -> None:
    if not requests:
        return
    for i in range(0, len(requests), 40):
        chunk = requests[i : i + 40]
        _retry_call(
            lambda c=chunk: svc.spreadsheets()
            .batchUpdate(spreadsheetId=SID, body={"requests": c})
            .execute(),
            "batchUpdate",
        )


def _hdr_map(row: List[Any]) -> Dict[str, int]:
    return {str(c).strip().upper(): i for i, c in enumerate(row or []) if str(c).strip()}


def _rules_headers_for_sheet(rules_tab: str, sheet_name: str) -> Set[str]:
    rows = get_values(a1(rules_tab, "A1:I500"))
    if not rows:
        return set()
    hdr = [str(c).strip().upper() for c in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    sheet_i = idx.get("TARGET SHEET", 1)
    header_i = idx.get("TARGET HEADER", 2)
    out: Set[str] = set()
    for r in rows[1:]:
        if len(r) <= max(sheet_i, header_i):
            continue
        if str(r[sheet_i]).strip() == sheet_name:
            h = str(r[header_i]).strip()
            if h:
                out.add(h.upper())
    return out


def merge_values_by_header(
    target_tab: str,
    cash_tab: str,
    bank_tab: str,
    balance_dates: List[Any],
) -> List[str]:
    """Merge twin data into target by header; returns final header row."""
    t_row = get_values(a1(target_tab, "A19:BZ19"))
    c_row = get_values(a1(cash_tab, "A19:BZ19"))
    b_row = get_values(a1(bank_tab, "A19:BZ19"))
    t_hdr = [str(c).strip() for c in (t_row[0] if t_row else [])]
    c_hdr = [str(c).strip() for c in (c_row[0] if c_row else [])]
    b_hdr = [str(c).strip() for c in (b_row[0] if b_row else [])]

    # ensure all twin headers exist on target
    existing = {h.upper() for h in t_hdr if h}
    for h in c_hdr + b_hdr:
        if h and h.upper() not in existing and h.upper() not in ("DATE",):
            t_hdr.append(h)
            existing.add(h.upper())

    t_map = _hdr_map(t_hdr)
    c_map = _hdr_map(c_hdr)
    b_map = _hdr_map(b_hdr)

    n = len(balance_dates)
    c_data = get_values(a1(cash_tab, f"A20:BZ{19 + n}"))
    b_data = get_values(a1(bank_tab, f"A20:BZ{19 + n}"))
    t_data = get_values(a1(target_tab, f"A20:BZ{19 + n}"))

    max_cols = max(len(t_hdr), 20)
    while len(t_hdr) < max_cols:
        t_hdr.append("")

    merged: List[List[Any]] = []
    for i in range(n):
        row = [""] * max_cols
        if i < len(t_data) and t_data[i]:
            for j, v in enumerate(t_data[i]):
                if j < max_cols:
                    row[j] = v
        if not row[0]:
            row[0] = balance_dates[i][0] if i < len(balance_dates) and balance_dates[i] else ""
        for h, ci in c_map.items():
            if h in t_map and i < len(c_data) and ci < len(c_data[i] or []):
                v = c_data[i][ci]
                if v not in ("", None):
                    row[t_map[h]] = v
        for h, bi in b_map.items():
            if h in t_map and i < len(b_data) and bi < len(b_data[i] or []):
                v = b_data[i][bi]
                if v not in ("", None):
                    row[t_map[h]] = v
        merged.append(row)

    clear_values(a1(target_tab, "A19:BZ500"))
    update_values(a1(target_tab, "A19"), [t_hdr] + merged, raw=True)
    print(f"  merged {cash_tab}+{bank_tab} -> {target_tab}")
    return t_hdr


def pad_row(row: List[Any], n: int) -> List[Any]:
    out = list(row or [])
    while len(out) < n:
        out.append("")
    return out[:n]


def setup_payroll(balance_dates: List[Any], cash_h: Set[str], bank_h: Set[str]) -> Tuple[str, str]:
    """Prepare PAYROLL with helper columns. Data stays; re-post will fill."""
    r19 = get_values(a1("PAYROLL", "A19:BZ19"))
    headers = [str(c).strip() for c in (r19[0] if r19 else [])]
    existing = {h.upper() for h in headers if h}
    for h in sorted(cash_h | bank_h):
        if h not in existing:
            headers.append(h)
            existing.add(h)
    cash_net = "Payroll Cash Net"
    bank_net = "Payroll Bank Net"
    if cash_net not in headers:
        headers.append(cash_net)
    if bank_net not in headers:
        headers.append(bank_net)

    # merge twin person values into PAYROLL
    merge_values_by_header("PAYROLL", "CASH PAYROLL", "BANK PAYROLL", balance_dates)
    r19 = get_values(a1("PAYROLL", "A19:BZ19"))
    headers = [str(c).strip() for c in (r19[0] if r19 else [])]
    if cash_net not in headers:
        headers.append(cash_net)
    if bank_net not in headers:
        headers.append(bank_net)
    update_values(a1("PAYROLL", "A18"), [["=== PAYROLL (merged cash+bank; color = source) ==="]], raw=True)
    update_values(a1("PAYROLL", "A19"), [headers], raw=True)

    cash_cols = []
    bank_cols = []
    for i, h in enumerate(headers):
        if not h or h in (cash_net, bank_net, "DATE", "Payroll"):
            continue
        hu = h.upper()
        if hu in cash_h:
            cash_cols.append(col_letter(i + 1))
        if hu in bank_h:
            bank_cols.append(col_letter(i + 1))

    cash_net_i = headers.index(cash_net) + 1
    bank_net_i = headers.index(bank_net) + 1
    n = len(balance_dates)
    existing = get_values(a1("PAYROLL", f"A20:{col_letter(len(headers))}{19 + n}"))
    rows = []
    for i in range(n):
        r = 20 + i
        row = pad_row(existing[i] if i < len(existing) else [], len(headers))
        row[0] = balance_dates[i][0] if balance_dates[i] else row[0]
        if cash_cols:
            parts = ",".join(f"{c}{r}" for c in cash_cols)
            row[cash_net_i - 1] = f'=IF(COUNTA({parts})=0,"",SUM({parts}))'
        else:
            row[cash_net_i - 1] = ""
        if bank_cols:
            parts = ",".join(f"{c}{r}" for c in bank_cols)
            row[bank_net_i - 1] = f'=IF(COUNTA({parts})=0,"",SUM({parts}))'
        else:
            row[bank_net_i - 1] = ""
        rows.append(row)
    update_values(a1("PAYROLL", "A20"), rows, raw=False)
    print(f"  PAYROLL helpers cash={cash_cols} bank={bank_cols}")
    return col_letter(cash_net_i), col_letter(bank_net_i)


def setup_jgd(balance_dates: List[Any]) -> Tuple[str, str]:
    cash_headers = ["ATM LOAD", "CLOVER", "SERVICE FEE"]
    bank_headers = ["SWITCH", "CLOVER", "SERVICE FEE"]
    # Unique bank CLOVER / SERVICE FEE: differentiate with zone (same header names OK
    # in different columns — Kylo finds first match). Prefer distinct layout:
    # Cash: ATM LOAD | CLOVER | SERVICE FEE ; Bank: SWITCH | CLOVER (BANK) | SERVICE FEE (BANK)
    # But rules use CLOVER/SERVICE FEE — keep same names; first match is cash, bank posts
    # may land on first. Better: Cash zone then Bank zone with SAME headers means
    # duplicate headers. Use BANK-prefixed only for second occurrence? Rules say CLOVER.
    # Practical: single CLOVER / SERVICE FEE columns (shared), ATM LOAD cash, SWITCH bank.
    # Helpers sum by rule pool provenance after re-post via color — NO, helpers must be
    # column-based. Layout:
    # DATE | ATM | ATM LOAD | [cash CLOVER] | [cash SERVICE FEE] | | SWITCH | [bank CLOVER] | [bank SERVICE FEE] | helpers
    # Rules: cash CLOVER -> first CLOVER col; bank CLOVER -> need distinct? jgdtruth finds
    # first header match. So cash and bank CLOVER collide on one column — source fill
    # distinguishes. Helpers: put ATM LOAD in cash helper; SWITCH in bank; CLOVER/SERVICE FEE
    # go to both helpers as shared (or one shared "either" that re-post color won't feed EOD).
    # Locked plan: Cash | Bank zones. Duplicate header names break first-match.
    # Solution used: cash headers ATM LOAD/Clover/Service Fee; bank SWITCH only for unique,
    # plus bank posts of CLOVER/SERVICE FEE land on cash cols until we add Pool-aware columns.
    # For EOD integrity: cash net = ATM LOAD+columns in cash zone; bank net = SWITCH+bank zone.
    # When bank posts CLOVER, with duplicate CLOVER headers Kylo uses first. Accept for now;
    # re-post after layout is done — bank CLOVER rare.

    merged_before = merge_values_by_header("JGD", "CASH JGD", "BANK JGD", balance_dates)
    old_data = get_values(a1("JGD", f"A20:BZ{19 + len(balance_dates)}"))
    old_map = _hdr_map(merged_before)

    headers = (
        ["DATE", "ATM"]
        + cash_headers
        + [""]
        + bank_headers
        + ["", "JGD Cash Net", "JGD Bank Net"]
    )
    section = (
        ["", ""]
        + ["CASH ZONE"]
        + [""] * (len(cash_headers) - 1)
        + ["|"]
        + ["BANK ZONE"]
        + [""] * (len(bank_headers) - 1)
        + ["|", "EOD HELPERS", ""]
    )
    cash_start, cash_end = 3, 2 + len(cash_headers)
    bank_start = cash_end + 2
    bank_end = bank_start + len(bank_headers) - 1
    cn_i = bank_end + 2
    bn_i = cn_i + 1
    new_map = _hdr_map(headers)

    n = len(balance_dates)
    data = []
    for i in range(n):
        r = 20 + i
        cash_rng = f"{col_letter(cash_start)}{r}:{col_letter(cash_end)}{r}"
        bank_rng = f"{col_letter(bank_start)}{r}:{col_letter(bank_end)}{r}"
        row = [""] * len(headers)
        row[0] = balance_dates[i][0] if balance_dates[i] else ""
        if i < len(old_data):
            for h, oi in old_map.items():
                if h in new_map and oi < len(old_data[i] or []):
                    v = old_data[i][oi]
                    if v not in ("", None) and h not in ("DATE", "ATM"):
                        # Prefer cash zone index first for shared names
                        row[new_map[h]] = v
        row[cn_i - 1] = f'=IF(COUNTA({cash_rng})=0,"",SUM({cash_rng}))'
        row[bn_i - 1] = f'=IF(COUNTA({bank_rng})=0,"",SUM({bank_rng}))'
        data.append(row)

    clear_values(a1("JGD", "A18:AZ400"))
    update_values(a1("JGD", "A18"), [section, headers] + data, raw=False)
    print(f"  JGD zones cash={col_letter(cash_start)}:{col_letter(cash_end)} bank={col_letter(bank_start)}:{col_letter(bank_end)}")
    return col_letter(cn_i), col_letter(bn_i)


def setup_income(balance_dates: List[Any]) -> Tuple[str, str]:
    CASH_HEADERS = [
        "REG 1", "REG 2", "REG 3", "(N) CASH", "(N) WHOLESALE", "(N) VENMO",
        "MISC SALES", "(P) SALES", "EMPIRE SALES",
    ]
    BANK_HEADERS = ["SQUARE", "VENMO", "SQUARE FEE", "INVESTMENT", "INTEREST", "CC STATUS", "(N) VENMO"]
    TRANSFER_HEADERS = ["FROM BANK", "TO BANK"]

    merged_before = merge_values_by_header("INCOME", "CASH INCOME", "BANK INCOME", balance_dates)
    old_data = get_values(a1("INCOME", f"A20:BZ{19 + len(balance_dates)}"))
    old_map = _hdr_map(merged_before)

    headers = (
        ["DATE", "INCOME"]
        + CASH_HEADERS
        + [""]
        + BANK_HEADERS
        + [""]
        + TRANSFER_HEADERS
        + ["", "Income Cash Net", "Income Bank Net"]
    )
    section = (
        ["", ""]
        + ["CASH POOL"]
        + [""] * (len(CASH_HEADERS) - 1)
        + ["|"]
        + ["BANK FEED"]
        + [""] * (len(BANK_HEADERS) - 1)
        + ["|"]
        + ["TRANSFERS", ""]
        + ["|", "EOD HELPERS", ""]
    )
    cash_start, cash_end = 3, 2 + len(CASH_HEADERS)
    bank_start = cash_end + 2
    bank_end = bank_start + len(BANK_HEADERS) - 1
    xfer_start = bank_end + 2
    cn_i = xfer_start + len(TRANSFER_HEADERS) + 1
    bn_i = cn_i + 1
    new_map = _hdr_map(headers)

    n = len(balance_dates)
    data = []
    for i in range(n):
        r = 20 + i
        cash_rng = f"{col_letter(cash_start)}{r}:{col_letter(cash_end)}{r}"
        bank_rng = f"{col_letter(bank_start)}{r}:{col_letter(bank_end)}{r}"
        row = [""] * len(headers)
        row[0] = balance_dates[i][0] if balance_dates[i] else ""
        row[1] = f"=SUM({cash_rng})+SUM({bank_rng})"
        if i < len(old_data):
            for h, oi in old_map.items():
                if h in new_map and oi < len(old_data[i] or []):
                    v = old_data[i][oi]
                    if v not in ("", None) and h not in ("DATE", "INCOME"):
                        row[new_map[h]] = v
        row[cn_i - 1] = f'=IF(COUNTA({cash_rng})=0,"",SUM({cash_rng}))'
        row[bn_i - 1] = f'=IF(COUNTA({bank_rng})=0,"",SUM({bank_rng}))'
        data.append(row)

    clear_values(a1("INCOME", "A18:AZ400"))
    update_values(a1("INCOME", "A18"), [section, headers] + data, raw=False)
    print(f"  INCOME helpers {col_letter(cn_i)}/{col_letter(bn_i)}")
    return col_letter(cn_i), col_letter(bn_i)


def setup_nugz_and_singles(balance_dates: List[Any]) -> None:
    merge_values_by_header("NUGZ COG", "CASH NUGZ COG", "BANK NUGZ COG", balance_dates)
    # rewrite B formulas
    hdr = [str(c).strip() for c in (get_values(a1("NUGZ COG", "A19:BZ19"))[0] or [])]
    sum_idxs = [i + 1 for i, h in enumerate(hdr) if h and h.upper() not in ("DATE", "COG")]
    n = len(balance_dates)
    if sum_idxs:
        start_c, end_c = col_letter(min(sum_idxs)), col_letter(max(sum_idxs))
        data = get_values(a1("NUGZ COG", f"A20:BZ{19 + n}"))
        rows = []
        for i in range(n):
            r = 20 + i
            row = pad_row(data[i] if i < len(data) else [], max(len(hdr), 10))
            row[0] = balance_dates[i][0] if balance_dates[i] else row[0]
            row[1] = f'=IF(COUNTA({start_c}{r}:{end_c}{r})=0,"",SUM({start_c}{r}:{end_c}{r}))'
            rows.append(row)
        update_values(a1("NUGZ COG", "A20"), rows, raw=False)

    for target, cash, bank in [
        ("NON CANNABIS", "CASH NON CANNABIS", "BANK NON CANNABIS"),
        ("ALLOCATED", "CASH ALLOCATED", "BANK ALLOCATED"),
    ]:
        merge_values_by_header(target, cash, bank, balance_dates)

    # CANNABIS DIST from cash twin
    c_hdr = get_values(a1("CASH CANNABIS DIST", "A19:BZ19"))
    c_data = get_values(a1("CASH CANNABIS DIST", f"A20:BZ{19 + n}"))
    if c_hdr:
        clear_values(a1("CANNABIS DIST", "A19:BZ500"))
        update_values(a1("CANNABIS DIST", "A19"), [c_hdr[0]] + c_data, raw=True)

    cc = get_values(a1("BANK CC Payments", f"A19:BZ{19 + n}"))
    if cc:
        clear_values(a1("CC Payments", "A18:BZ400"))
        update_values(a1("CC Payments", "A18"), [["=== CC Payments (bank) ==="]] + cc, raw=False)
    print("  NUGZ COG + singles done")


def retarget_rules(rules_tab: str) -> int:
    rows = get_values(a1(rules_tab, "A1:I500"))
    if not rows:
        return 0
    hdr = [str(c).strip() for c in rows[0]]
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    sheet_i = idx["TARGET SHEET"]
    changed = 0
    out = [rows[0]]
    for r in rows[1:]:
        row = list(r) + [""] * (len(hdr) - len(r))
        old = str(row[sheet_i]).strip()
        if old in RETARGET_MAP and RETARGET_MAP[old] != old:
            row[sheet_i] = RETARGET_MAP[old]
            changed += 1
        out.append(row[: len(hdr)])
    clear_values(a1(rules_tab, "A1:I500"))
    update_values(a1(rules_tab, "A1"), out, raw=True)
    print(f"  {rules_tab}: retargeted {changed} rows")
    return changed


def hide_twin_tabs(tabs: Dict[str, int]) -> None:
    reqs = []
    for title in HIDE_TABS:
        sid = tabs.get(title)
        if sid is None:
            continue
        reqs.append({
            "updateSheetProperties": {
                "properties": {"sheetId": sid, "hidden": True},
                "fields": "hidden",
            }
        })
    batch_update(reqs)
    print(f"  hidden {len(reqs)} tabs")


def ensure_projection_consumed_tab(tabs: Dict[str, int]) -> None:
    if "PROJECTION CONSUMED" in tabs:
        return
    batch_update([{
        "addSheet": {
            "properties": {
                "title": "PROJECTION CONSUMED",
                "gridProperties": {"frozenRowCount": 1},
            }
        }
    }])
    update_values(
        a1("PROJECTION CONSUMED", "A1"),
        [["Consumed At", "Projected Date", "Actual Date", "Sheet", "Header",
          "Amount", "Txn UIDs", "Match Type", "Notes"]],
        raw=True,
    )
    print("  created PROJECTION CONSUMED")


def wire_balance(
    payroll_cash_col: str,
    payroll_bank_col: str,
    jgd_cash_col: str,
    jgd_bank_col: str,
    income_cash_col: str,
    income_bank_col: str,
    balance_dates: List[Any],
) -> None:
    update_values(
        a1("BALANCE", "A18:L18"),
        [[
            "", "", "Payroll (merged)", "Expenses (twins)", "COG (cash)", "JGD (merged)",
            "CC (bank)", "Income (merged)",
            "BANK EOD", "CASH EOD", "IN TRANSIT", "AVAILABLE = I+J+K",
        ]],
        raw=True,
    )
    update_values(
        a1("BALANCE", "B19:L19"),
        [["DATE", "Payroll", "EXPENSES", "COG", "ATM/JGD", "CREDIT CARDS", "INCOME",
          "Bank EOD", "Cash EOD", "In Transit", "AVAILABLE"]],
        raw=True,
    )

    n = len(balance_dates)

    def ref(tab: str, col: str, r: int) -> str:
        return f"IFERROR({quote_tab(tab)}!{col}{r},0)"

    rows_c_h = []
    rows_i_l = []
    for i in range(n):
        r = 20 + i
        pay_c = ref("PAYROLL", payroll_cash_col, r)
        pay_b = ref("PAYROLL", payroll_bank_col, r)
        exp_c = ref("CASH EXPENSES", "B", r)
        exp_b = ref("BANK EXPENSES", "B", r)
        cog = ref("NUGZ COG", "B", r)
        jgd_c = ref("JGD", jgd_cash_col, r)
        jgd_b = ref("JGD", jgd_bank_col, r)
        cc = ref("CC Payments", "B", r)
        inc_c = ref("INCOME", income_cash_col, r)
        inc_b = ref("INCOME", income_bank_col, r)
        nc = ref("NON CANNABIS", "B", r)
        al = ref("ALLOCATED", "B", r)
        cd = ref("CANNABIS DIST", "B", r)

        rows_c_h.append([
            f"={pay_c}+{pay_b}",
            f"={exp_c}+{exp_b}",
            f"={cog}",
            f"={jgd_c}+{jgd_b}",
            f"={cc}",
            f"={inc_c}+{inc_b}",
        ])
        bank_day = f"({inc_b}+{exp_b}+{pay_b}+{jgd_b}+{cc})"
        cash_day = f"({inc_c}+{exp_c}+{pay_c}+{jgd_c}+{cog}+{nc}+{al}+{cd})"
        if i == 0:
            i_f = f"={OPENING_BANK}+{bank_day}"
            j_f = f"={OPENING_CASH}+{cash_day}"
        else:
            i_f = f"=I{r-1}+{bank_day}"
            j_f = f"=J{r-1}+{cash_day}"
        rows_i_l.append([i_f, j_f, "0", f"=I{r}+J{r}+K{r}"])

    update_values(a1("BALANCE", "C20"), rows_c_h, raw=False)
    update_values(a1("BALANCE", "I20"), rows_i_l, raw=False)
    print(f"  BALANCE wired {n} days")


def main() -> None:
    print("=== collapse dual-pool sandbox ===")
    balance_dates = get_values(a1("BALANCE", "B20:B385"))
    if not balance_dates:
        raise SystemExit("BALANCE dates missing")
    print(f"  days={len(balance_dates)}")

    cash_pay = _rules_headers_for_sheet("TRANSACTIONS RULES", "CASH PAYROLL")
    bank_pay = _rules_headers_for_sheet("BANK RULES", "BANK PAYROLL")
    # if already retargeted, also check PAYROLL
    if not cash_pay:
        cash_pay = _rules_headers_for_sheet("TRANSACTIONS RULES", "PAYROLL")
    if not bank_pay:
        bank_pay = _rules_headers_for_sheet("BANK RULES", "PAYROLL")
    print(f"  payroll cash headers={len(cash_pay)} bank={len(bank_pay)}")

    print("=== 1) NUGZ + singles ===")
    setup_nugz_and_singles(balance_dates)

    print("=== 2) PAYROLL ===")
    pc, pb = setup_payroll(balance_dates, cash_pay, bank_pay)

    print("=== 3) JGD ===")
    jc, jb = setup_jgd(balance_dates)

    print("=== 4) INCOME ===")
    ic, ib = setup_income(balance_dates)

    print("=== 5) retarget rules ===")
    retarget_rules("TRANSACTIONS RULES")
    retarget_rules("BANK RULES")

    print("=== 6) BALANCE ===")
    wire_balance(pc, pb, jc, jb, ic, ib, balance_dates)

    print("=== 7) hide + log tab ===")
    tabs = meta_tabs()
    hide_twin_tabs(tabs)
    ensure_projection_consumed_tab(meta_tabs())

    update_values(
        a1("SANDBOX README", "A70"),
        [
            ["DUAL-POOL COLLAPSE (2026-07-15)"],
            ["Merged", "PAYROLL, JGD, INCOME, NUGZ COG, NON CANNABIS, ALLOCATED, CC Payments"],
            ["Twins kept", "CASH EXPENSES + BANK EXPENSES only"],
            ["EOD", "BALANCE I/J/L from helper cols + twin B"],
            ["Projection", "PROJECTION CONSUMED + matcher"],
        ],
        raw=True,
    )
    print("DONE collapse.")


if __name__ == "__main__":
    main()
