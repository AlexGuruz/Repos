"""
Formula-driven dashboard_data + meta for projection Google Sheet (exclusion filter).

Executive KPI column (AC) is mostly **values** from Python (``lib.projection_exec_kpis``); row 1 (**total pool**) is a **formula** that uses ``dashboard!S1`` when set, else the Python total.

filtered_layer2 lives at dashboard_data!A2500 (dynamic-array spill). Helpers must NOT use Excel-style spill refs
(A2500#, AD3#): Google Sheets treats those as formula parse errors. Use COUNTA + OFFSET over bounded ranges instead.
raw_layer2 body ranges must end at row (1 + CSV rows)—never literal A2:ZZ unbounded (ROWS becomes sheet-sized).
Body rows skip the header via OFFSET from row (FILTERED_LAYER2_ROW_1BASED+1) with height (_fl_n-1); DROP() is not available in all Sheets builds. Do not use A1# spill refs.
Brand/category column detection uses LOWER(header) so Title Case CSV headers still resolve.
When the filter matches no rows, filtered_layer2 spills the header row only (no synthetic "No data" body row).
Filter UI cells: dashboard!M1 (mode), dashboard!O1 (value), dashboard!Q1 (summary text).
O1 with mode Brand or Category: list multiple exclusions separated by | (pipe). Brand+Category: separate pairs with || .
Optional pool KPI display override: dashboard!S1 (number); blank uses CSV total (dashboard_data!AC3 formula).
"""
from __future__ import annotations

from typing import Any

# Must stay below all formula helpers; room for spill rows under API limits.
FILTERED_LAYER2_ROW_1BASED = 2500
# Empty rows appended after the A2500 formula in the pushed grid: spill (header + filtered CSV rows) must fit,
# and values.update must overwrite any stale cells that would otherwise block #SPILL!.
FILTERED_LAYER2_TAIL_ROWS = 800
FILTERED_LAYER2_LAST_ROW_1BASED = FILTERED_LAYER2_ROW_1BASED + FILTERED_LAYER2_TAIL_ROWS - 1
# dashboard_data tab grid is capped (e.g. 40 cols); OFFSET width must match so INDEX(d,0,k) aligns with spill.
DASHBOARD_DATA_SPILL_WIDTH = 40
# Unique lists (AD/AF) and O1 list (AB): scan down to sheet limit so COUNTA captures full spill.
UNIQUE_COL_SCAN_END_ROW = 3300
# Column AB (28) = dynamic list for data validation on dashboard!O1
DYN_LIST_COL_LETTER = "AB"
UNIQUE_BRAND_COL = "AD"
UNIQUE_CAT_COL = "AE"
UNIQUE_BC_COL = "AF"
# KPI snapshot values (Python → column AC = 29)
KPI_COL_LETTER = "AC"
KPI_ROW_1BASED = 3
# Row 1–2 = filter helper banner + labels; row 3 = AB (O1 list spill), AD:AF (unique lists), AC (KPI start).
FILTER_HELPERS_ROW_1BASED = KPI_ROW_1BASED


def _match_col_ci_raw1(*, raw_quoted: str, col_lower: str) -> str:
    """Column index on raw_layer2 row 1 (case-insensitive). Use A1:ZZ1 — never $1:$1 (grid-wide row breaks XMATCH/MATCH)."""
    return f'MATCH(TRUE,ARRAYFORMULA(LOWER({raw_quoted}!A1:ZZ1)="{col_lower}"),0)'


def letters_to_idx0(col_letters: str) -> int:
    n = 0
    for ch in col_letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def _esc_sheet(name: str) -> str:
    if "'" in name:
        return "'" + name.replace("'", "''") + "'"
    return f"'{name}'"


# Column indices for helpers/KPIs: MATCH against raw row 1 (not dynamic spill header CHOOSEROWS — fragile in Sheets).
RAW_LAYER2_HDR_A1 = f"{_esc_sheet('raw_layer2')}!A1:ZZ1"

# Optional numeric pool display override (does not change allocations in raw_layer2).
POOL_OVERRIDE_CELL = f"{_esc_sheet('dashboard')}!$S$1"

_SPILL_HEADER_BRAND = f'MATCH("brand",{RAW_LAYER2_HDR_A1},0)'
_SPILL_HEADER_CATEGORY = f'MATCH("category",{RAW_LAYER2_HDR_A1},0)'


def _raw_body_range_a1(*, raw_quoted: str, raw_last_row_1based: int) -> str:
    """Bounded CSV body on raw_layer2 (row 1 = header). Unbounded A2:ZZ makes ROWS(r) grid-sized and breaks SEQUENCE/FILTER."""
    end_r = max(2, int(raw_last_row_1based))
    return f"{raw_quoted}!A2:ZZ{end_r}"


def filtered_layer2_formula(*, raw_last_row_1based: int) -> str:
    """Spill: header + body rows, or header only if filter removes all rows (avoids fake 'No data' body)."""
    dash = _esc_sheet("dashboard")
    raw = _esc_sheet("raw_layer2")
    r_range = _raw_body_range_a1(raw_quoted=raw, raw_last_row_1based=raw_last_row_1based)
    # Brand/Category: O1 may list several tokens separated by | . Brand+Category: pairs separated by || .
    return (
        f'=LET('
        f'h,{raw}!A1:ZZ1,'
        f'r,{r_range},'
        f'mode,TRIM({dash}!$M$1),'
        f'val,TRIM({dash}!$O$1),'
        f'bc,MATCH(TRUE,ARRAYFORMULA(LOWER(h)="brand"),0),'
        f'cc,MATCH(TRUE,ARRAYFORMULA(LOWER(h)="category"),0),'
        f'pass,IF('
        f'OR(LOWER(mode)="none",mode="",val=""),'
        f'SEQUENCE(ROWS(r),1,1,1),'
        f'IF(TRIM(mode)="Brand",'
        f'BYROW(SEQUENCE(ROWS(r)),LAMBDA(i,LET('
        f'b,INDEX(r,i,bc),sp,TRIM(SPLIT(val,"|")),tok,FILTER(sp,LEN(sp)>0),'
        f'IFERROR(IF(ISNUMBER(MATCH(b,tok,0)),0,1),1)))),'
        f'IF(TRIM(mode)="Category",'
        f'BYROW(SEQUENCE(ROWS(r)),LAMBDA(i,LET('
        f'c,INDEX(r,i,cc),sp,TRIM(SPLIT(val,"|")),tok,FILTER(sp,LEN(sp)>0),'
        f'IFERROR(IF(ISNUMBER(MATCH(c,tok,0)),0,1),1)))),'
        f'IF(TRIM(mode)="Brand+Category",'
        f'BYROW(SEQUENCE(ROWS(r)),LAMBDA(i,LET('
        f'rown,INDEX(r,i,bc)&" | "&INDEX(r,i,cc),sp,TRIM(SPLIT(val,"||")),pr,FILTER(sp,LEN(sp)>0),'
        f'IFERROR(IF(ISNUMBER(MATCH(rown,pr,0)),0,1),1)))),'
        f'SEQUENCE(ROWS(r),1,1,1))))),'
        f'f,FILTER(r,pass),'
        f'IF(ROWS(f)>0,VSTACK(h,f),h))'
    )


def unique_brand_formula(*, raw_last_row_1based: int) -> str:
    raw = _esc_sheet("raw_layer2")
    body = _raw_body_range_a1(raw_quoted=raw, raw_last_row_1based=raw_last_row_1based)
    m = _match_col_ci_raw1(raw_quoted=raw, col_lower="brand")
    return (
        f'=LET(bc,{m},SORT(UNIQUE(FILTER(INDEX({body},0,bc),LEN(INDEX({body},0,bc))>0)),1,TRUE))'
    )


def unique_category_formula(*, raw_last_row_1based: int) -> str:
    raw = _esc_sheet("raw_layer2")
    body = _raw_body_range_a1(raw_quoted=raw, raw_last_row_1based=raw_last_row_1based)
    m = _match_col_ci_raw1(raw_quoted=raw, col_lower="category")
    return (
        f'=LET(cc,{m},SORT(UNIQUE(FILTER(INDEX({body},0,cc),LEN(INDEX({body},0,cc))>0)),1,TRUE))'
    )


def unique_brand_category_formula(*, raw_last_row_1based: int) -> str:
    raw = _esc_sheet("raw_layer2")
    body = _raw_body_range_a1(raw_quoted=raw, raw_last_row_1based=raw_last_row_1based)
    return (
        f'=LET('
        f'bc,{_match_col_ci_raw1(raw_quoted=raw, col_lower="brand")},'
        f'cc,{_match_col_ci_raw1(raw_quoted=raw, col_lower="category")},'
        f'b,INDEX({body},0,bc),'
        f'c,INDEX({body},0,cc),'
        f'pair,b&" | "&c,'
        f'SORT(UNIQUE(FILTER(pair,LEN(pair)>0)),1,TRUE))'
    )


def _unique_column_spill_expr(*, col_letter: str, row_1based: int) -> str:
    """Bounded column block for a vertical spill (replaces ColRow# — # is not valid in Google Sheets)."""
    r0 = row_1based
    r1 = UNIQUE_COL_SCAN_END_ROW
    z1 = _make_empty_row_matrix(1)
    return (
        f'IF(COUNTA({col_letter}{r0}:{col_letter}{r1})=0,'
        f'{z1},'
        f'OFFSET({col_letter}{r0},0,0,COUNTA({col_letter}{r0}:{col_letter}{r1}),1))'
    )


def _make_empty_row_matrix(cols: int) -> str:
    """Single blank row; MAKEARRAY(0,cols,...) is invalid in Google Sheets."""
    return f'MAKEARRAY(1,{cols},LAMBDA(__e_r,__e_c,""))'


def _first_k_rows_block(*, array_expr: str, k_cap: int) -> str:
    """First k rows of array_expr; TAKE() is unavailable in some Sheets builds."""
    return (
        f'LET(__fk_sd,{array_expr},__fk_kr,MIN({k_cap},ROWS(__fk_sd)),'
        f'IF(__fk_kr<1,MAKEARRAY(1,COLUMNS(__fk_sd),LAMBDA(__fk_a,__fk_b,"")),'
        f'CHOOSEROWS(__fk_sd,SEQUENCE(__fk_kr))))'
    )


def _label_from_brand_category_expr(
    *,
    brand_expr: str,
    category_expr: str,
    brand_chars: int,
    category_chars: int,
) -> str:
    """Row-wise brand/category label text; avoids scalar LEFT() behavior across array rows."""
    return (
        f'BYROW(HSTACK({brand_expr},{category_expr}),LAMBDA(_lbl_r,'
        f'LEFT(INDEX(_lbl_r,1,1),{int(brand_chars)})&" / "&'
        f'LEFT(INDEX(_lbl_r,1,2),{int(category_chars)})))'
    )


def dynamic_o1_list_formula() -> str:
    dash = _esc_sheet("dashboard")
    r = FILTER_HELPERS_ROW_1BASED
    m = f'TRIM({dash}!$M$1)'
    # Branches must all return compatible spill types (same column shape).
    zero_col = _make_empty_row_matrix(1)
    b = _unique_column_spill_expr(col_letter=UNIQUE_BRAND_COL, row_1based=r)
    c = _unique_column_spill_expr(col_letter=UNIQUE_CAT_COL, row_1based=r)
    bc = _unique_column_spill_expr(col_letter=UNIQUE_BC_COL, row_1based=r)
    return (
        f'=LET(m,{m},'
        f'IF(m="Brand",{b},'
        f'IF(m="Category",{c},'
        f'IF(m="Brand+Category",{bc},{zero_col}))))'
    )


def _filtered_layer_rowcount_binding() -> str:
    """Row count for filtered_layer2 spill (column A); avoids A2500# (parse error in Google Sheets)."""
    r0 = FILTERED_LAYER2_ROW_1BASED
    r1 = FILTERED_LAYER2_LAST_ROW_1BASED
    return f'_fl_n,COUNTA(A{r0}:A{r1})'


# Body matrix under the header row (A2500). Uses grid OFFSET, not DROP (unsupported in some Sheets).
FILTERED_BODY_DROP = (
    f'd,IF(_fl_n<=1,{_make_empty_row_matrix(DASHBOARD_DATA_SPILL_WIDTH)},'
    f'OFFSET(A{FILTERED_LAYER2_ROW_1BASED + 1},0,0,_fl_n-1,{DASHBOARD_DATA_SPILL_WIDTH})),'
)
FILTERED_HEADER_ROW = ""


def recovery_col_let_var(use_days: bool) -> str:
    rh = RAW_LAYER2_HDR_A1
    if use_days:
        return (
            f'recCol,IFERROR(MATCH("cash_recovery_days",{rh},0),MATCH("months_to_recover_cog",{rh},0)),'
        )
    return f'recCol,MATCH("months_to_recover_cog",{rh},0),'


def _pad_recovery_display_expr(*, use_days: bool) -> str:
    """Per-row recovery column for ranking spills built on ``pad``.

    In buy-plan day mode, ``cash_recovery_days`` is cash-cycle capped and often clusters near
    the cap; show **COG payback via gross profit** = allocated × cash_recovery_days / gross_profit
    so tables reflect margin + velocity differences without changing table shape.
    """
    if not use_days:
        return "INDEX(pad,0,recCol)"
    return (
        "BYROW(SEQUENCE(ROWS(pad)),LAMBDA(_ri,LET("
        "_a,INDEX(pad,_ri,ac),_r,INDEX(pad,_ri,recCol),_g,INDEX(pad,_ri,gp),"
        'IF(AND(ISNUMBER(_a),ISNUMBER(_r),ISNUMBER(_g),_g>0),IFERROR(_a*_r/_g,""),""))))'
    )


def _worst_recovery_sorted_dm_expr(*, use_days: bool) -> str:
    """Sort meaningful rows for WORST table: months mode by recCol; day mode by GP payback days."""
    if not use_days:
        return "SORT(dm,recCol,FALSE)"
    return (
        "LET(ws,COLS(dm),pb,BYROW(SEQUENCE(ROWS(dm)),LAMBDA(i,LET("
        "a,INDEX(dm,i,ac),r,INDEX(dm,i,recCol),g,INDEX(dm,i,gp),"
        'IF(AND(ISNUMBER(a),ISNUMBER(r),ISNUMBER(g),g>0),IFERROR(a*r/g,""),"")))),'
        "ARRAY_CONSTRAIN(SORT(HSTACK(dm,pb),ws+1,FALSE),ROWS(dm),ws))"
    )


def alloc_top_formula_resolved(*, table_top_n: int, use_days: bool) -> str:
    rc = recovery_col_let_var(use_days)
    fb = _filtered_layer_rowcount_binding()
    return (
        f'=LET('
        f'{fb},'
        f'{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},'
        f'cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'n,MAX(0,_fl_n-1),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(d,ac,FALSE)", k_cap=table_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={table_top_n},s,'
        f'VSTACK(s,MAKEARRAY({table_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'{_pad_recovery_display_expr(use_days=use_days)},INDEX(pad,0,ef)'
        f'))),'
        f'top)'
    )


def gp_top_formula(*, table_top_n: int, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'n,MAX(0,_fl_n-1),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(d,gp,FALSE)", k_cap=table_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={table_top_n},s,'
        f'VSTACK(s,MAKEARRAY({table_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'{_pad_recovery_display_expr(use_days=use_days)},INDEX(pad,0,ef)'
        f'))),top)'
    )


def weak_high_dollar_formula(
    *, high_dollar_usd: float, meaningful_usd: float, use_days: bool
) -> str:
    """High-$ meaningful rows, lowest efficiency first (matches prior dashboard weak table)."""
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
        f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,ac)>={high_dollar_usd})*(INDEX(d,i,ef)<>""))),'
        f'dm,FILTER(d,mask),'
        f'n,ROWS(dm),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(dm,ef,TRUE)", k_cap=8)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>=8,s,VSTACK(s,MAKEARRAY(8-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'{_pad_recovery_display_expr(use_days=use_days)},INDEX(pad,0,ef)'
        f'))),top)'
    )


def eff_top_formula(*, table_top_n: int, meaningful_usd: float, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
        f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,ef)<>""))),'
        f'dm,FILTER(d,mask),'
        f'n,ROWS(dm),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(dm,ef,FALSE)", k_cap=table_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={table_top_n},s,'
        f'VSTACK(s,MAKEARRAY({table_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'{_pad_recovery_display_expr(use_days=use_days)},INDEX(pad,0,ef)'
        f'))),top)'
    )


def worst_recovery_formula(*, table_top_n: int, meaningful_usd: float, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    wsort = _worst_recovery_sorted_dm_expr(use_days=use_days)
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
        f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,recCol)<>""))),'
        f'dm,FILTER(d,mask),'
        f'n,ROWS(dm),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr=wsort, k_cap=table_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={table_top_n},s,'
        f'VSTACK(s,MAKEARRAY({table_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'{_pad_recovery_display_expr(use_days=use_days)},INDEX(pad,0,ef)'
        f'))),top)'
    )


def fast_recovery_chart_formula(*, chart_top_n: int, meaningful_usd: float, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    if use_days:
        # In buy-plan mode, allocated dollars are cash-cycle capped, so cash_recovery_days tends to flatten.
        # Rank by observed sales velocity to reflect true brand×category timing differences.
        return (
            f'=LET('
            f'{fb},{FILTERED_HEADER_ROW}'
            f'{FILTERED_BODY_DROP}'
            f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
            f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
            f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
            f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
            f'upd,MATCH("avg_units_per_day",{RAW_LAYER2_HDR_A1},0),'
            f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
            f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
            f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,upd)<>""))),'
            f'dm,FILTER(d,mask),'
            f'n,ROWS(dm),'
            f'top,IF(n=0,{_make_empty_row_matrix(8)},'
            f'LET(s,{_first_k_rows_block(array_expr="SORT(dm,upd,FALSE)", k_cap=chart_top_n)},'
            f'nr,ROWS(s),'
            f'pad,IF(nr>={chart_top_n},s,'
            f'VSTACK(s,MAKEARRAY({chart_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
            f'HSTACK('
            f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
            f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
            f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
            f'INDEX(pad,0,upd),INDEX(pad,0,ef)'
            f'))),top)'
        )
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
        f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,recCol)<>""))),'
        f'dm,FILTER(d,mask),'
        f'n,ROWS(dm),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(dm,recCol,TRUE)", k_cap=chart_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={chart_top_n},s,'
        f'VSTACK(s,MAKEARRAY({chart_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=18, category_chars=14)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),'
        f'INDEX(pad,0,ac),INDEX(pad,0,rv),INDEX(pad,0,gp),'
        f'INDEX(pad,0,recCol),INDEX(pad,0,ef)'
        f'))),top)'
    )


def category_summary_formula(*, meaningful_usd: float, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    u = meaningful_usd
    # Buy-plan: never multiply whole-column INDEX(d,0,k) vectors (Sheets can mis-broadcast vs BYROW mask,
    # zeroing wm_den/we_den and blanking payback + efficiency). Sum with REDUCE over row ri instead.
    mm_ri = f"(TRIM(INDEX(d,ri,cc))=catv)*(INDEX(d,ri,ac)>={u:g})"
    weighted_buy_plan = (
        f"wm_den,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),m,INDEX(d,ri,recCol),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(m)),a,0)))),"
        f"pay_w_num,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),m,INDEX(d,ri,recCol),g,INDEX(d,ri,gp),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(m),g>0),IFERROR(a*m/g,0),0)))),"
        f'wa_m,IF(wm_den>0,IFERROR(pay_w_num/wm_den,""),""),'
        f"we_num,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),e,INDEX(d,ri,ef),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(e)),e*a,0)))),"
        f"we_den,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),e,INDEX(d,ri,ef),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(e)),a,0)))),"
        f'wa_e,IF(we_den>0,IFERROR(we_num/we_den,""),""),'
    )
    weighted_months = (
        f"meaningful,mask*(alloc>={u:g}),"
        f"mo,INDEX(d,0,recCol),"
        f"efv,INDEX(d,0,ef),"
        f'wm_den,SUM(FILTER(alloc,meaningful*(mo<>""))),'
        f'wa_m,IF(wm_den>0,SUM(FILTER(mo*alloc,meaningful*(mo<>"")))/wm_den,""),'
        f'we_den,SUM(FILTER(alloc,meaningful*(efv<>""))),'
        f'wa_e,IF(we_den>0,IFERROR(SUM(FILTER(IFERROR(efv*alloc,0),meaningful*(efv<>"")))/we_den,""),""),'
    )
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'rv,MATCH("projected_revenue_from_allocated_units_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'cats,SORT(UNIQUE(FILTER(INDEX(d,0,cc),LEN(INDEX(d,0,cc))>0)),1,TRUE),'
        f'BYROW(cats,LAMBDA(cat,LET('
        f'catv,TRIM(INDEX(cat,1,1)),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(ri,TRIM(INDEX(d,ri,cc))=catv)),'
        f'alloc,INDEX(d,0,ac),'
        f'm_alloc,SUM(FILTER(alloc,mask)),'
        f'm_rev,SUM(FILTER(INDEX(d,0,rv),mask)),'
        f'm_gp,SUM(FILTER(INDEX(d,0,gp),mask)),'
        f'cnt,SUMPRODUCT(--mask),'
        f'{weighted_buy_plan if use_days else weighted_months}'
        f'HSTACK(cat,m_alloc,wa_m,wa_e,m_rev,m_gp,cnt)'
        f'))))'
    )


def brand_summary_formula(*, table_top_n: int, meaningful_usd: float, use_days: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    u = meaningful_usd
    mm_ri = f"(TRIM(INDEX(d,ri,bc))=bv)*(INDEX(d,ri,ac)>={u:g})"
    weighted_buy_plan = (
        f"wm_den,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),m,INDEX(d,ri,recCol),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(m)),a,0)))),"
        f"pay_w_num,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),m,INDEX(d,ri,recCol),g,INDEX(d,ri,gp),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(m),g>0),IFERROR(a*m/g,0),0)))),"
        f'wa_m,IF(wm_den>0,IFERROR(pay_w_num/wm_den,""),""),'
        f"we_num,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),e,INDEX(d,ri,ef),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(e)),e*a,0)))),"
        f"we_den,REDUCE(0,SEQUENCE(ROWS(d)),LAMBDA(acc,ri,LET(a,INDEX(d,ri,ac),e,INDEX(d,ri,ef),"
        f"mm,{mm_ri},acc+IF(AND(mm,ISNUMBER(e)),a,0)))),"
        f'wa_e,IF(we_den>0,IFERROR(we_num/we_den,""),""),'
    )
    weighted_months = (
        f"meaningful,mask*(alloc>={u:g}),"
        f"mo,INDEX(d,0,recCol),"
        f"efv,INDEX(d,0,ef),"
        f'wm_den,SUM(FILTER(alloc,meaningful*(mo<>""))),'
        f'wa_m,IF(wm_den>0,SUM(FILTER(mo*alloc,meaningful*(mo<>"")))/wm_den,""),'
        f'we_den,SUM(FILTER(alloc,meaningful*(efv<>""))),'
        f'wa_e,IF(we_den>0,IFERROR(SUM(FILTER(IFERROR(efv*alloc,0),meaningful*(efv<>"")))/we_den,""),""),'
    )
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'gp,MATCH("projected_gross_profit_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'brands,SORT(UNIQUE(FILTER(INDEX(d,0,bc),LEN(INDEX(d,0,bc))>0)),1,TRUE),'
        f'alloc_by,BYROW(brands,LAMBDA(b,SUM(FILTER(INDEX(d,0,ac),INDEX(d,0,bc)=b)))),'
        f'ord,SORT(HSTACK(brands,alloc_by),2,FALSE),'
        f'topb,IF(ROWS(ord)=0,{_make_empty_row_matrix(2)},{_first_k_rows_block(array_expr="ord", k_cap=table_top_n)}),'
        f'IF(ROWS(topb)=0,{_make_empty_row_matrix(5)},'
        f'BYROW(topb,LAMBDA(row,LET('
        f'b,INDEX(row,,1),'
        f'm_alloc,INDEX(row,,2),'
        f'bv,TRIM(b),'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(ri,TRIM(INDEX(d,ri,bc))=bv)),'
        f'alloc,INDEX(d,0,ac),'
        f'm_gp,SUM(FILTER(INDEX(d,0,gp),mask)),'
        f'{weighted_buy_plan if use_days else weighted_months}'
        f'HSTACK(b,m_alloc,m_gp,wa_m,wa_e)'
        f')))))'
    )


def bucket_summary_formula(*, use_days: bool, use_status_buckets: bool) -> str:
    fb = _filtered_layer_rowcount_binding()
    bcol = "cash_cycle_status" if use_status_buckets else "recovery_bucket"
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bk,MATCH("{bcol}",{RAW_LAYER2_HDR_A1},0),'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'keys,INDEX(d,0,bk),'
        f'u,SORT(UNIQUE(FILTER(keys,LEN(keys)>0)),1,TRUE),'
        f'BYROW(u,LAMBDA(k,LET('
        f'm,INDEX(d,0,bk)=k,'
        f'HSTACK(k,SUMPRODUCT(--m),SUM(FILTER(INDEX(d,0,ac),m)))'
        f'))))'
    )


def scatter_chart_formula(
    *,
    meaningful_usd: float,
    use_days: bool,
    scatter_max_months: float,
    scatter_max_days: float,
    scatter_cap_rows: int,
) -> str:
    fb = _filtered_layer_rowcount_binding()
    rc = recovery_col_let_var(use_days)
    cap = scatter_max_days if use_days else scatter_max_months
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'{rc}'
        f'ef,MATCH("allocation_efficiency",{RAW_LAYER2_HDR_A1},0),'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'mask,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,'
        f'(INDEX(d,i,ac)>={meaningful_usd})*(INDEX(d,i,recCol)<>"")*(INDEX(d,i,ef)<>"")*(INDEX(d,i,recCol)<={cap}))),'
        f'dm,FILTER(d,mask),'
        f'n,ROWS(dm),'
        f's,IF(n=0,MAKEARRAY(1,COLUMNS(d),LAMBDA(__sc_r,__sc_c,"")),'
        f'{_first_k_rows_block(array_expr="SORT(dm,ac,FALSE)", k_cap=scatter_cap_rows)}),'
        f'HSTACK(INDEX(s,0,recCol),INDEX(s,0,ef),INDEX(s,0,ac),INDEX(s,0,bc),INDEX(s,0,cc)))'
    )


def spend_ledger_formula() -> str:
    """Sorted brand × category lines (no brand subtotals; reflects filtered_layer2)."""
    fb = _filtered_layer_rowcount_binding()
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'p,HSTACK(INDEX(d,0,bc),INDEX(d,0,cc),INDEX(d,0,ac)),'
        f'pf,FILTER(p,BYROW(SEQUENCE(ROWS(p)),LAMBDA(i,LEN(INDEX(p,i,1))+LEN(INDEX(p,i,2))>0))),'
        f'IF(ROWS(pf)=0,{_make_empty_row_matrix(3)},SORT(pf,1,TRUE,3,FALSE)))'
    )


def velocity_detail_table_formula() -> str:
    """All funded lines sorted by brand, category (dashboard Sale velocity table)."""
    fb = _filtered_layer_rowcount_binding()
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'upd,MATCH("avg_units_per_day",{RAW_LAYER2_HDR_A1},0),'
        f'wk,MATCH("avg_units_per_week",{RAW_LAYER2_HDR_A1},0),'
        f'wst,MATCH("weeks_to_sell_through",{RAW_LAYER2_HDR_A1},0),'
        f'vwd,IFERROR(MATCH("velocity_window_days",{RAW_LAYER2_HDR_A1},0),MATCH("velocity_window_days_run",{RAW_LAYER2_HDR_A1},0)),'
        f'p,HSTACK('
        f'INDEX(d,0,bc),INDEX(d,0,cc),INDEX(d,0,upd),INDEX(d,0,wk),INDEX(d,0,wst),INDEX(d,0,vwd),INDEX(d,0,ac)'
        f'),'
        f'pf,FILTER(p,BYROW(SEQUENCE(ROWS(p)),LAMBDA(i,INDEX(p,i,7)>0))),'
        f'SORT(pf,1,TRUE,2,TRUE)))'
    )


def velocity_chart_formula(*, chart_top_n: int) -> str:
    fb = _filtered_layer_rowcount_binding()
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'upd,MATCH("avg_units_per_day",{RAW_LAYER2_HDR_A1},0),'
        f'wk,MATCH("avg_units_per_week",{RAW_LAYER2_HDR_A1},0),'
        f'wst,MATCH("weeks_to_sell_through",{RAW_LAYER2_HDR_A1},0),'
        f'vwd,IFERROR(MATCH("velocity_window_days",{RAW_LAYER2_HDR_A1},0),MATCH("velocity_window_days_run",{RAW_LAYER2_HDR_A1},0)),'
        f'n,MAX(0,_fl_n-1),'
        f'top,IF(n=0,{_make_empty_row_matrix(8)},'
        f'LET(s,{_first_k_rows_block(array_expr="SORT(d,ac,FALSE)", k_cap=chart_top_n)},'
        f'nr,ROWS(s),'
        f'pad,IF(nr>={chart_top_n},s,'
        f'VSTACK(s,MAKEARRAY({chart_top_n}-nr,COLUMNS(s),LAMBDA(_r,_c,"")))),'
        f'HSTACK('
        f'{_label_from_brand_category_expr(brand_expr="INDEX(pad,0,bc)", category_expr="INDEX(pad,0,cc)", brand_chars=16, category_chars=12)},'
        f'INDEX(pad,0,bc),INDEX(pad,0,cc),INDEX(pad,0,ac),'
        f'INDEX(pad,0,upd),INDEX(pad,0,wk),INDEX(pad,0,wst),INDEX(pad,0,vwd)'
        f'))),top)'
    )


def back_stock_formula(*, table_top_n: int) -> str:
    fb = _filtered_layer_rowcount_binding()
    return (
        f'=LET('
        f'{fb},{FILTERED_HEADER_ROW}'
        f'{FILTERED_BODY_DROP}'
        f'bc,{_SPILL_HEADER_BRAND},cc,{_SPILL_HEADER_CATEGORY},'
        f'ac,MATCH("allocated_cog_usd",{RAW_LAYER2_HDR_A1},0),'
        f'upd,MATCH("avg_units_per_day",{RAW_LAYER2_HDR_A1},0),'
        f'u7,MATCH("units_needed_7d",{RAW_LAYER2_HDR_A1},0),'
        f'u14,MATCH("units_needed_14d",{RAW_LAYER2_HDR_A1},0),'
        f'u21,MATCH("units_needed_21d",{RAW_LAYER2_HDR_A1},0),'
        f'ufa,MATCH("units_from_allocation",{RAW_LAYER2_HDR_A1},0),'
        f'doc,MATCH("days_of_cover",{RAW_LAYER2_HDR_A1},0),'
        f'cov,MATCH("cover_status",{RAW_LAYER2_HDR_A1},0),'
        f'crd,MATCH("cash_recovery_days",{RAW_LAYER2_HDR_A1},0),'
        f'st,MATCH("cash_cycle_status",{RAW_LAYER2_HDR_A1},0),'
        f'maxc,MATCH("max_cog_allowed_usd",{RAW_LAYER2_HDR_A1},0),'
        f'capb,MATCH("capped_by_cash_cycle",{RAW_LAYER2_HDR_A1},0),'
        f'has,BYROW(SEQUENCE(ROWS(d)),LAMBDA(i,((INDEX(d,i,u7)<>"")+(INDEX(d,i,upd)<>""))>0)),'
        f'dm,FILTER(d,has),'
        f's,IF(ROWS(dm)<1,{_make_empty_row_matrix(DASHBOARD_DATA_SPILL_WIDTH)},'
        f'{_first_k_rows_block(array_expr="SORT(dm,ac,FALSE)", k_cap=table_top_n)}),'
        f'HSTACK('
        f'INDEX(s,0,bc),INDEX(s,0,cc),INDEX(s,0,ac),'
        f'INDEX(s,0,upd),INDEX(s,0,u7),INDEX(s,0,u14),INDEX(s,0,u21),'
        f'INDEX(s,0,ufa),INDEX(s,0,doc),INDEX(s,0,cov),INDEX(s,0,crd),'
        f'INDEX(s,0,st),INDEX(s,0,maxc),INDEX(s,0,capb)'
        f'))'
    )


def build_dashboard_data_formula_grid(
    *,
    headers: list[str],
    rows: list[dict[str, str]],
    table_top_n: int,
    chart_top_n: int,
    meaningful_usd: float,
    high_dollar_usd: float,
    scatter_max_months: float,
    scatter_max_days: float,
    scatter_cap_rows: int,
    kpi_ac_values: list[Any],
) -> tuple[list[list[Any]], dict[str, Any]]:
    """Builds tall dashboard_data grid; filtered_layer2 at row FILTERED_LAYER2_ROW_1BASED."""

    def _fnum_local(x: str | None) -> float | None:
        if x is None or str(x).strip() == "":
            return None
        try:
            return float(x)
        except ValueError:
            return None

    def _use_days_axis(rws: list[dict[str, str]]) -> bool:
        if not rws or (rws[0].get("allocation_mode") or "").strip() != "buy-plan":
            return False
        return any(_fnum_local(r.get("cash_recovery_days")) is not None for r in rws)

    use_days = _use_days_axis(rows)
    is_buy_plan = bool(rows) and (rows[0].get("allocation_mode") or "").strip() == "buy-plan"
    use_status_buckets = use_days and any((r.get("cash_cycle_status") or "").strip() for r in rows)
    n_cols = max(len(headers), 32)
    anchor_idx = FILTERED_LAYER2_ROW_1BASED - 1

    def empty_row() -> list[Any]:
        return [""] * n_cols

    grid: list[list[Any]] = []
    meta: dict[str, Any] = {
        "recovery_axis_days": use_days,
        "total_pool_alloc_usd": sum(_fnum_local(r.get("allocated_cog_usd")) or 0 for r in rows),
    }
    # raw_layer2: row 1 = header; data rows 2..(1+len(rows)). Never use unbounded A2:ZZ (ROWS hits grid size).
    raw_last_row_1based = max(2, 1 + len(rows))
    meta["raw_data_end_row_1based"] = raw_last_row_1based

    def push_row(cells: list[Any]) -> None:
        r = empty_row()
        for i, v in enumerate(cells):
            if i < n_cols:
                r[i] = v
        grid.append(r)

    def skip_rows(n: int) -> None:
        for _ in range(n):
            grid.append(empty_row())

    # --- Filter helper rows 1–2 (labels); row FILTER_HELPERS_ROW_1BASED = AB spill + AD:AF uniques + KPI AC
    rh0 = empty_row()
    rh0[0] = "EXCLUSION FILTER HELPERS (lists for dashboard O1; do not delete)"
    grid.append(rh0)
    rh1 = empty_row()
    rh1[27] = "dynamic_list_for_O1 →"
    rh1[29] = "unique_brand_list →"
    rh1[30] = "unique_category_list →"
    rh1[31] = "unique_brand_category_list →"
    grid.append(rh1)
    rh2 = empty_row()
    rh2[27] = dynamic_o1_list_formula()
    rh2[29] = unique_brand_formula(raw_last_row_1based=raw_last_row_1based)
    rh2[30] = unique_category_formula(raw_last_row_1based=raw_last_row_1based)
    rh2[31] = unique_brand_category_formula(raw_last_row_1based=raw_last_row_1based)
    grid.append(rh2)

    # KPI column AC: row 1 = pool formula (Python total + optional dashboard!S1); others = Python values
    meta["kpi_formula_start_row"] = KPI_ROW_1BASED
    meta["kpi_formula_col_letter"] = KPI_COL_LETTER
    meta["kpi_formula_col_index"] = letters_to_idx0(KPI_COL_LETTER)
    meta["kpi_ac_value_count"] = len(kpi_ac_values)

    kpi_ci = letters_to_idx0(KPI_COL_LETTER)
    while len(grid) < KPI_ROW_1BASED - 1:
        grid.append(empty_row())
    for i, kval in enumerate(kpi_ac_values):
        while len(grid) <= KPI_ROW_1BASED - 1 + i:
            grid.append(empty_row())
        row = grid[KPI_ROW_1BASED - 1 + i]
        while len(row) < n_cols:
            row.append("")
        if i == 0 and isinstance(kval, (int, float)):
            row[kpi_ci] = (
                f"=LET(_csvp,{float(kval)},_ov,{POOL_OVERRIDE_CELL},"
                f'IF(LEN(TRIM(_ov))=0,_csvp,IFERROR(VALUE(_ov),_csvp)))'
            )
        else:
            row[kpi_ci] = kval

    def append_formula_section(
        title: str,
        hdr: list[str],
        formula: str,
        *,
        meta_prefix: str,
        data_rows: int,
    ) -> None:
        skip_rows(1)
        push_row([title])
        tr = len(grid) - 1
        push_row(hdr)
        hr = len(grid) - 1
        push_row([formula] + [""] * (n_cols - 1))
        dr = len(grid) - 1
        # Reserve rows for dynamic-array spill (formula row counts as row 1 of the spill).
        skip_rows(max(0, int(data_rows) - 1))
        skip_rows(1)
        meta[f"{meta_prefix}_header_row"] = hr
        meta[f"{meta_prefix}_data_start"] = dr
        meta[f"{meta_prefix}_data_end"] = dr + data_rows - 1
        _ = tr

    alloc_f = alloc_top_formula_resolved(table_top_n=table_top_n, use_days=use_days)
    append_formula_section(
        "ALLOC_TOP (sorted by allocated_cog_usd; from filtered_layer2)",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "gross_profit_payback_days" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        alloc_f,
        meta_prefix="alloc",
        data_rows=table_top_n,
    )

    append_formula_section(
        "GP_TOP (sorted by projected_gross_profit_usd)",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "gross_profit_payback_days" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        gp_top_formula(table_top_n=min(10, table_top_n), use_days=use_days),
        meta_prefix="gp",
        data_rows=10,
    )

    append_formula_section(
        f"EFF_TOP_MEANINGFUL (allocated_cog_usd >= {meaningful_usd:g})",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "gross_profit_payback_days" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        eff_top_formula(
            table_top_n=table_top_n, meaningful_usd=meaningful_usd, use_days=use_days
        ),
        meta_prefix="eff",
        data_rows=table_top_n,
    )

    append_formula_section(
        f"WEAK_HIGH_DOLLAR (Allocated COG ≥ {high_dollar_usd:g}, lowest efficiency first)",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "gross_profit_payback_days" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        weak_high_dollar_formula(
            high_dollar_usd=high_dollar_usd,
            meaningful_usd=meaningful_usd,
            use_days=use_days,
        ),
        meta_prefix="weak_margin",
        data_rows=8,
    )

    append_formula_section(
        f"WORST_RECOVERY_MEANINGFUL (allocated_cog_usd >= {meaningful_usd:g})",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "gross_profit_payback_days" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        worst_recovery_formula(
            table_top_n=table_top_n, meaningful_usd=meaningful_usd, use_days=use_days
        ),
        meta_prefix="worst",
        data_rows=table_top_n,
    )

    cat_hdr = [
        "category",
        "total_allocated_usd",
        (
            "wavg_gp_payback_days_meaningful"
            if use_days
            else "wavg_months_recover_meaningful"
        ),
        "wavg_efficiency_meaningful",
        "projected_revenue_usd",
        "projected_gross_profit_usd",
        "row_count",
    ]
    # Spill height for category summary (and pie chart, which reads cols A–B of this block).
    n_unique_cat = len(
        {(r.get("category") or "").strip() for r in rows if (r.get("category") or "").strip()}
    )
    cat_rows = min(max(n_unique_cat + 25, len(rows) + 15, 80), 500)
    append_formula_section(
        "CATEGORY_SUMMARY (from filtered_layer2; pie chart uses cols A–B of this spill)",
        cat_hdr,
        category_summary_formula(meaningful_usd=meaningful_usd, use_days=use_days),
        meta_prefix="cat",
        data_rows=cat_rows,
    )
    # Pie chart must not include padded blank spill rows (empty col B → "Column 2 must be numeric").
    meta["n_unique_categories"] = int(n_unique_cat)

    append_formula_section(
        "BRAND_SUMMARY_TOP20 (from filtered_layer2)",
        [
            "brand",
            "total_allocated_usd",
            "projected_gross_profit_usd",
            (
                "wavg_gp_payback_days_meaningful"
                if use_days
                else "wavg_months_recover_meaningful"
            ),
            "wavg_efficiency_meaningful",
        ],
        brand_summary_formula(
            table_top_n=table_top_n, meaningful_usd=meaningful_usd, use_days=use_days
        ),
        meta_prefix="brand",
        data_rows=table_top_n,
    )

    bk_hdr = [
        "cash_cycle_status" if use_status_buckets else "recovery_bucket",
        "row_count",
        "total_allocated_usd",
    ]
    append_formula_section(
        (
            "LINE_COUNT_BY_CASH_CYCLE_STATUS (SAFE / WARNING / CAPITAL RISK = funded lines)"
            if use_status_buckets
            else "LINE_COUNT_BY_RECOVERY_BUCKET (month-based thresholds from layer2)"
        ),
        bk_hdr,
        bucket_summary_formula(use_days=use_days, use_status_buckets=use_status_buckets),
        meta_prefix="bucket",
        data_rows=12,
    )

    sc_hdr = [
        "cash_recovery_days" if use_days else "months_to_recover_cog",
        "allocation_efficiency",
        "allocated_cog_usd",
        "brand",
        "category",
    ]
    append_formula_section(
        f"SCATTER_MEANINGFUL (alloc>={meaningful_usd:g})",
        sc_hdr,
        scatter_chart_formula(
            meaningful_usd=meaningful_usd,
            use_days=use_days,
            scatter_max_months=scatter_max_months,
            scatter_max_days=scatter_max_days,
            scatter_cap_rows=scatter_cap_rows,
        ),
        meta_prefix="scatter",
        data_rows=scatter_cap_rows,
    )

    append_formula_section(
        f"FAST_RECOVERY_TOP_{chart_top_n}_FOR_CHART (meaningful alloc>={meaningful_usd:g}, fastest first)",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "projected_revenue_from_allocated_units_usd",
            "projected_gross_profit_usd",
            "avg_units_per_day" if use_days else "months_to_recover_cog",
            "allocation_efficiency",
        ],
        fast_recovery_chart_formula(
            chart_top_n=chart_top_n,
            meaningful_usd=meaningful_usd,
            use_days=use_days,
        ),
        meta_prefix="fast_recovery",
        data_rows=chart_top_n,
    )

    append_formula_section(
        "VELOCITY_TOP_FOR_CHART (top allocated rows; from filtered_layer2)",
        [
            "label",
            "brand",
            "category",
            "allocated_cog_usd",
            "avg_units_per_day",
            "avg_units_per_week",
            "weeks_to_sell_through",
            "velocity_window_days",
        ],
        velocity_chart_formula(chart_top_n=chart_top_n),
        meta_prefix="vel_chart",
        data_rows=chart_top_n,
    )

    append_formula_section(
        "DEPLOYMENT_LEDGER_SORTED (filtered; no brand subtotals)",
        ["Brand", "Category", "Pool spend (Allocated COG)"],
        spend_ledger_formula(),
        meta_prefix="spend_ledger",
        data_rows=220,
    )

    append_formula_section(
        "BRAND_CATEGORY_VELOCITY (filtered; all funded lines)",
        [
            "Brand",
            "Category",
            "Avg units / day",
            "Avg units / week",
            "Weeks to sell this buy",
            "Velocity window (days)",
            "Allocated COG",
        ],
        velocity_detail_table_formula(),
        meta_prefix="velocity",
        data_rows=400,
    )

    # Back-stock (optional columns — formula errors if column missing; layer2 CSV always has them in buy-plan)
    try:
        _ = headers.index("units_needed_7d")
        append_formula_section(
            "BACK_STOCK_DEMAND_BY_TIME (buy-plan metrics; filtered)",
            [
                "brand",
                "category",
                "allocated_cog_usd",
                "avg_units_per_day",
                "units_needed_7d",
                "units_needed_14d",
                "units_needed_21d",
                "units_from_allocation",
                "days_of_cover",
                "cover_status",
                "cash_recovery_days",
                "cash_cycle_status",
                "max_cog_allowed_usd",
                "capped_by_cash_cycle",
            ],
            back_stock_formula(table_top_n=table_top_n),
            meta_prefix="back_stock",
            data_rows=table_top_n,
        )
    except ValueError:
        pass

    meta["use_status_buckets"] = use_status_buckets

    if len(grid) > anchor_idx:
        raise ValueError(
            f"dashboard_data sections exceed row {FILTERED_LAYER2_ROW_1BASED}; raise FILTERED_LAYER2_ROW_1BASED "
            f"or reduce sections (len={len(grid)})"
        )

    # Pad to anchor (need rows through index anchor_idx inclusive)
    while len(grid) < anchor_idx + 1:
        grid.append(empty_row())
    grid[anchor_idx - 1][0] = "filtered_layer2 (spill below; do not paste over)"
    grid[anchor_idx][0] = filtered_layer2_formula(raw_last_row_1based=raw_last_row_1based)

    for _ in range(FILTERED_LAYER2_TAIL_ROWS):
        grid.append(empty_row())

    meta["filtered_layer2_row_1based"] = FILTERED_LAYER2_ROW_1BASED
    meta["dyn_list_col"] = DYN_LIST_COL_LETTER
    return grid, meta
