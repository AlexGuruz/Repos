from __future__ import annotations

from typing import Dict
from src.gsheets import a1, norm, ensure_id


def load_rules(svc, cfg: dict) -> Dict[str, str]:
    kylo_id = ensure_id(cfg["kylo_id"])
    tab = cfg["kylo_tab"]
    k_col = cfg["kylo_clean_col"]
    m_col = cfg["kylo_company_col"]
    n_col = cfg.get("kylo_active_col")
    limit = cfg["rows_read_limit"]

    end_col = n_col or m_col
    rng = a1(tab, 2, k_col, limit, end_col)
    vals = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=kylo_id, range=rng)
        .execute()
        .get("values", [])
    )

    rules: Dict[str, str] = {}
    for row in vals:
        clean = row[0] if len(row) >= 1 else ""
        comp = row[m_col - k_col] if len(row) >= (m_col - k_col + 1) else ""
        ok = True
        if n_col:
            idx = n_col - k_col
            ok = len(row) > idx and str(row[idx]).strip().upper() == "TRUE"
        if clean and comp and ok:
            rules[norm(clean)] = str(comp)
    return rules
