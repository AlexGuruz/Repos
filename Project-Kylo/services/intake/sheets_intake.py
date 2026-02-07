from __future__ import annotations

import csv
import io
import re
from typing import Any, Iterable, List, Optional


def quote_tab_a1(tab_name: str) -> str:
    """Quote a sheet tab title for A1 notation when needed.

    The Sheets API requires quotes around tab names that contain spaces or
    special characters, e.g. \"'JGD EXPENSES'!A1\".
    """
    s = str(tab_name or "")
    if re.search(r"[^A-Za-z0-9_]", s):
        return "'" + s.replace("'", "''") + "'"
    return s


def find_last_ready_row(col_a_values: List[List[Any]], *, header_rows: int = 1) -> int:
    """Return the 1-based index of the last non-empty row in Column A.

    `col_a_values` should be the `values` payload from Sheets API for a 1-column range,
    e.g. reading `TAB!A:A`.

    If there are no ready rows after the header, returns 0.
    """
    last = 0
    for idx_1, row in enumerate(col_a_values, start=1):
        if idx_1 <= int(header_rows):
            continue
        v = None
        try:
            v = row[0] if row else None
        except Exception:
            v = None
        if v is None:
            continue
        if str(v).strip() == "":
            continue
        last = idx_1
    return int(last)


def values_to_csv(values: List[List[Any]]) -> str:
    """Convert a 2D values array into a CSV string with correct quoting."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for row in values:
        # Ensure rectangular-ish output: Sheets can return ragged rows.
        if row is None:
            w.writerow([])
        else:
            w.writerow([("" if v is None else v) for v in row])
    return buf.getvalue()


def build_bounded_range(tab_name: str, *, last_row: int, last_col: str = "Z") -> str:
    """Build a bounded A1 range for a tab, safely quoting tab names."""
    qt = quote_tab_a1(tab_name)
    lr = int(last_row)
    if lr <= 0:
        lr = 1
    lc = str(last_col or "Z").strip().upper()
    if not re.match(r"^[A-Z]{1,3}$", lc):
        lc = "Z"
    return f"{qt}!A1:{lc}{lr}"

