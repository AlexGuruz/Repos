"""
Projection consumption: clear ahead-of-date manual literals when a matching
actual posts within a configurable date window.

See docs/DUAL_POOL_TARGET_MODEL.md for the locked contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from services.common.retry import google_api_execute
from services.state.store import State, compute_cell_key


@dataclass
class ActualCell:
    tab: str
    header: str
    date_key: str  # M/D/YY
    amount: float
    txn_uids: Set[str] = field(default_factory=set)
    a1: str = ""


@dataclass
class ProjectionCandidate:
    tab: str
    header: str
    date_key: str
    amount: float
    a1: str


@dataclass
class ProjectionMatch:
    projected: ProjectionCandidate
    actual: ActualCell
    match_type: str  # drift_consume | same_day_overwrite | partial | ambiguous
    score: float
    notes: str = ""


@dataclass
class ProjectionMatchResult:
    consumed: List[ProjectionMatch] = field(default_factory=list)
    review_queue: List[ProjectionMatch] = field(default_factory=list)
    cleared_a1s: List[str] = field(default_factory=list)


def _cfg_block(cfg: Any, path: str) -> dict:
    """Read a nested config dict; supports LayeredConfig .get('a.b') and plain dicts."""
    if cfg is None:
        return {}
    # Prefer dotted get (Kylo layered config)
    try:
        got = cfg.get(path)
        if isinstance(got, dict):
            return got
    except Exception:
        pass
    cur: Any = cfg
    for part in path.split("."):
        if not isinstance(cur, dict):
            return {}
        cur = cur.get(part)
        if cur is None:
            return {}
    return cur if isinstance(cur, dict) else {}


def projection_match_config(cfg: Any) -> dict:
    block = _cfg_block(cfg, "posting.projection_match")
    return {
        "enabled": bool(block.get("enabled", False)),
        "window_days": int(block.get("window_days", 2) or 2),
        "amount_tolerance": float(block.get("amount_tolerance", 0.02) or 0.02),
        "clear_on_match": bool(block.get("clear_on_match", True)),
        "review_on_ambiguous": bool(block.get("review_on_ambiguous", True)),
        "include_tabs": list(block.get("include_tabs") or []),
        "log_tab": str(block.get("log_tab") or "PROJECTION CONSUMED"),
    }


def _parse_mdy(mdy: str) -> Optional[date]:
    s = str(mdy or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if not m:
        return None
    yy = int(m.group(3))
    if yy >= 100:
        yy = yy % 100
    return date(2000 + yy, int(m.group(1)), int(m.group(2)))


def _format_mdy(dt: date) -> str:
    return f"{dt.month}/{dt.day}/{dt.year % 100:02d}"


def _same_sign(a: float, b: float) -> bool:
    if a == 0 or b == 0:
        return True
    return (a > 0) == (b > 0)


def _amount_close(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol + 1e-9


def _score_match(proj_date: date, actual_date: date, proj_amt: float, actual_amt: float) -> float:
    """Higher is better. Exact amount beats near amount; nearer date wins."""
    amt_pen = abs(proj_amt - actual_amt)
    day_pen = abs((proj_date - actual_date).days)
    same_month_bonus = 10.0 if proj_date.month == actual_date.month and proj_date.year == actual_date.year else 0.0
    return 1000.0 - amt_pen * 100.0 - day_pen * 10.0 + same_month_bonus


def find_projection_matches(
    actuals: Sequence[ActualCell],
    projections: Sequence[ProjectionCandidate],
    *,
    window_days: int = 2,
    amount_tolerance: float = 0.02,
) -> ProjectionMatchResult:
    """Pure matcher: pair actuals to orphan projections."""
    result = ProjectionMatchResult()
    used_proj: Set[str] = set()

    for actual in actuals:
        actual_dt = _parse_mdy(actual.date_key)
        if actual_dt is None:
            continue
        candidates: List[Tuple[float, ProjectionCandidate]] = []
        for proj in projections:
            if proj.a1 in used_proj:
                continue
            if proj.tab != actual.tab or proj.header != actual.header:
                continue
            if proj.date_key == actual.date_key:
                continue  # same-day handled by poster overwrite
            if not _same_sign(proj.amount, actual.amount):
                continue
            proj_dt = _parse_mdy(proj.date_key)
            if proj_dt is None:
                continue
            if abs((proj_dt - actual_dt).days) > window_days:
                continue
            if not _amount_close(proj.amount, actual.amount, amount_tolerance):
                continue
            sc = _score_match(proj_dt, actual_dt, proj.amount, actual.amount)
            candidates.append((sc, proj))

        if not candidates:
            # partial: projection exists nearby but amount off?
            for proj in projections:
                if proj.a1 in used_proj:
                    continue
                if proj.tab != actual.tab or proj.header != actual.header:
                    continue
                if proj.date_key == actual.date_key:
                    continue
                if not _same_sign(proj.amount, actual.amount):
                    continue
                proj_dt = _parse_mdy(proj.date_key)
                if proj_dt is None:
                    continue
                if abs((proj_dt - actual_dt).days) > window_days:
                    continue
                if _amount_close(proj.amount, actual.amount, amount_tolerance):
                    continue
                result.review_queue.append(
                    ProjectionMatch(
                        projected=proj,
                        actual=actual,
                        match_type="partial",
                        score=0.0,
                        notes=f"amount delta {abs(proj.amount - actual.amount):.2f}",
                    )
                )
            continue

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_score = candidates[0][0]
        tied = [c for sc, c in candidates if abs(sc - top_score) < 0.01]
        if len(tied) > 1:
            for proj in tied:
                result.review_queue.append(
                    ProjectionMatch(
                        projected=proj,
                        actual=actual,
                        match_type="ambiguous",
                        score=top_score,
                        notes="top candidates tied",
                    )
                )
            continue

        winner = candidates[0][1]
        used_proj.add(winner.a1)
        result.consumed.append(
            ProjectionMatch(
                projected=winner,
                actual=actual,
                match_type="drift_consume",
                score=top_score,
            )
        )
        result.cleared_a1s.append(winner.a1)

    return result


def _quote_tab(name: str) -> str:
    s = str(name or "")
    if re.search(r"[^A-Za-z0-9_]", s):
        return "'" + s.replace("'", "''") + "'"
    return s


def _col_to_a1(col_index_0: int) -> str:
    s = ""
    n = col_index_0 + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _parse_number(raw: Any) -> Optional[float]:
    if raw in ("", None):
        return None
    try:
        return float(str(raw).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _read_tab_headers(
    service,
    spreadsheet_id: str,
    tab: str,
    header_row: int = 19,
) -> List[str]:
    rng = f"{_quote_tab(tab)}!A{header_row}:BZ{header_row}"
    resp = google_api_execute(
        service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=rng,
            valueRenderOption="UNFORMATTED_VALUE",
        ),
        label="projection:read_headers",
    )
    row = resp.get("values", [[]])
    return [str(c).strip() for c in (row[0] if row else [])]


def _read_tab_date_map(
    service,
    spreadsheet_id: str,
    tab: str,
    first_row: int = 20,
) -> Dict[str, int]:
    rng = f"{_quote_tab(tab)}!A{first_row}:A{first_row + 400}"
    resp = google_api_execute(
        service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=rng,
            valueRenderOption="FORMATTED_VALUE",
        ),
        label="projection:read_dates",
    )
    out: Dict[str, int] = {}
    for i, row in enumerate(resp.get("values", [])):
        if not row:
            continue
        key = str(row[0]).strip()
        dt = _parse_mdy(key)
        if dt:
            key = _format_mdy(dt)
        if key and key not in out:
            out[key] = first_row + i
    return out


def collect_orphan_projections(
    service,
    spreadsheet_id: str,
    cfg: Any,
    company_id: str,
    state: State,
    *,
    exclude_a1s: Optional[Set[str]] = None,
    header_row: int = 19,
    first_row: int = 20,
    scope_actuals: Optional[Sequence[ActualCell]] = None,
    window_days: int = 2,
) -> List[ProjectionCandidate]:
    """Scan near actual posts for numeric cells not explained by Kylo signatures.

    When ``scope_actuals`` is provided, only checks the same tab+header within
    ±window_days of each actual (avoids treating full-year REG1 grids as A/P).
    """
    skip_headers = {
        "DATE", "INCOME", "EXPENSES", "PAYROLL", "COG", "ATM", "CREDIT CARDS",
        "TOTAL", "PAYROLL CASH NET", "PAYROLL BANK NET", "JGD CASH NET", "JGD BANK NET",
        "INCOME CASH NET", "INCOME BANK NET",
    }
    orphans: List[ProjectionCandidate] = []
    exclude = exclude_a1s or set()

    if not scope_actuals:
        return orphans

    # Group needed lookups: tab -> {(header, date_key)...}
    needed: Dict[str, Set[Tuple[str, str]]] = {}
    for actual in scope_actuals:
        actual_dt = _parse_mdy(actual.date_key)
        if actual_dt is None:
            continue
        for delta in range(-window_days, window_days + 1):
            if delta == 0:
                continue  # same-day is poster overwrite
            dk = _format_mdy(actual_dt + timedelta(days=delta))
            needed.setdefault(actual.tab, set()).add((actual.header, dk))

    for tab, pairs in needed.items():
        headers = _read_tab_headers(service, spreadsheet_id, tab, header_row)
        date_map = _read_tab_date_map(service, spreadsheet_id, tab, first_row)
        if not date_map:
            continue
        ranges: List[str] = []
        meta: List[Tuple[str, str, str]] = []
        for header, date_key in pairs:
            if not header or header.upper() in skip_headers:
                continue
            # first matching header column (zone layouts may duplicate names)
            col_i = None
            for i, h in enumerate(headers):
                if str(h).strip().lower() == header.strip().lower():
                    col_i = i
                    break
            if col_i is None:
                continue
            row_i = date_map.get(date_key)
            if row_i is None:
                continue
            a1 = f"{_quote_tab(tab)}!{_col_to_a1(col_i)}{row_i}"
            if a1 in exclude:
                continue
            ck = compute_cell_key(tab, header, date_key, spreadsheet_id=spreadsheet_id)
            if state.get_signature(company_id, ck):
                continue
            ranges.append(a1)
            meta.append((tab, header, date_key))
        if not ranges:
            continue
        chunk = 80
        for i in range(0, len(ranges), chunk):
            batch = ranges[i : i + chunk]
            resp = google_api_execute(
                service.spreadsheets().values().batchGet(
                    spreadsheetId=spreadsheet_id,
                    ranges=batch,
                    valueRenderOption="UNFORMATTED_VALUE",
                ),
                label="projection:scan_orphans",
            )
            for j, vr in enumerate(resp.get("valueRanges", [])):
                idx = i + j
                if idx >= len(meta):
                    break
                tab_m, header_m, date_m = meta[idx]
                vals = vr.get("values", [])
                amt = _parse_number(vals[0][0] if vals and vals[0] else None)
                if amt is None:
                    continue
                a1 = batch[j] if j < len(batch) else ranges[idx]
                orphans.append(
                    ProjectionCandidate(
                        tab=tab_m,
                        header=header_m,
                        date_key=date_m,
                        amount=amt,
                        a1=a1,
                    )
                )
    return orphans


def apply_projection_consumption(
    service,
    spreadsheet_id: str,
    cfg: Any,
    company_id: str,
    state: State,
    actual_cells: Sequence[ActualCell],
    *,
    header_row: int = 19,
    first_row: int = 20,
) -> ProjectionMatchResult:
    """Find drifted projection matches, clear projection cells, log + persist state."""
    pm = projection_match_config(cfg)
    if not pm["enabled"]:
        return ProjectionMatchResult()

    actual_a1s = {a.a1 for a in actual_cells if a.a1}
    orphans = collect_orphan_projections(
        service,
        spreadsheet_id,
        cfg,
        company_id,
        state,
        exclude_a1s=actual_a1s,
        header_row=header_row,
        first_row=first_row,
        scope_actuals=actual_cells,
        window_days=pm["window_days"],
    )
    match_result = find_projection_matches(
        actual_cells,
        orphans,
        window_days=pm["window_days"],
        amount_tolerance=pm["amount_tolerance"],
    )

    if not match_result.consumed:
        return match_result

    dry = not bool(_cfg_block(cfg, "posting.sheets").get("apply", True))
    if dry:
        return match_result

    clear_data = []
    log_rows = []
    for m in match_result.consumed:
        if pm["clear_on_match"]:
            clear_data.append({"range": m.projected.a1, "values": [[""]]})
        uids = ",".join(sorted(m.actual.txn_uids))
        log_rows.append([
            _format_mdy(date.today()),
            m.projected.date_key,
            m.actual.date_key,
            m.projected.tab,
            m.projected.header,
            m.projected.amount,
            uids,
            m.match_type,
            f"cleared {m.projected.a1}",
        ])
        state.add_projection_consumption(
            company_id,
            {
                "projected_a1": m.projected.a1,
                "actual_a1": m.actual.a1,
                "projected_date": m.projected.date_key,
                "actual_date": m.actual.date_key,
                "sheet": m.projected.tab,
                "header": m.projected.header,
                "amount": m.projected.amount,
                "txn_uids": sorted(m.actual.txn_uids),
                "match_type": m.match_type,
            },
        )

    if clear_data and pm["clear_on_match"]:
        google_api_execute(
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": clear_data},
            ),
            label="projection:clear_cells",
        )

    if log_rows:
        log_tab = pm["log_tab"]
        google_api_execute(
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{_quote_tab(log_tab)}!A:I",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": log_rows},
            ),
            label="projection:log_consumed",
        )

    try:
        print(
            f"[PROJECTION] consumed={len(match_result.consumed)} "
            f"review={len(match_result.review_queue)}"
        )
    except Exception:
        pass
    return match_result


def actuals_from_posting(
    cell_totals: Dict[str, int],
    cell_meta: Dict[str, Tuple[str, str, str]],
    cell_txns: Dict[str, Set[str]],
    posted_ranges: Set[str],
) -> List[ActualCell]:
    """Build ActualCell list from poster aggregates for ranges written this run."""
    out: List[ActualCell] = []
    for a1 in sorted(posted_ranges):
        total_cents = cell_totals.get(a1)
        meta = cell_meta.get(a1)
        if total_cents is None or not meta:
            continue
        tab, header, date_key = meta
        out.append(
            ActualCell(
                tab=tab,
                header=header,
                date_key=date_key,
                amount=round(total_cents / 100.0, 2),
                txn_uids=set(cell_txns.get(a1) or set()),
                a1=a1,
            )
        )
    return out


__all__ = [
    "ActualCell",
    "ProjectionCandidate",
    "ProjectionMatch",
    "ProjectionMatchResult",
    "apply_projection_consumption",
    "actuals_from_posting",
    "collect_orphan_projections",
    "find_projection_matches",
    "projection_match_config",
]
