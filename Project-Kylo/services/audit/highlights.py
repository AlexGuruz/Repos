from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from services.audit.row_model import ChangeEvent
from services.common.retry import google_api_execute


def _norm_tab_key(value: str) -> str:
    s = str(value or "")
    try:
        s = unicodedata.normalize("NFKC", s)
    except Exception:
        pass
    s = s.replace("\u200b", "").replace("\u200c", "").replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _rgb_from_cfg(block: Dict[str, object], key: str, default: Tuple[float, float, float]) -> Dict[str, float]:
    raw = block.get(key, default)
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        try:
            r, g, b = (float(raw[0]), float(raw[1]), float(raw[2]))
        except Exception:
            r, g, b = default
    else:
        r, g, b = default
    for x in (r, g, b):
        if x < 0 or x > 1:
            r, g, b = default
            break
    return {"red": r, "green": g, "blue": b}


def _color_for_event(event: ChangeEvent, colors: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    if "FALSE_PAYROLL" in event.anomalies or "INFLATED_PAYROLL_APPEARANCE" in event.anomalies:
        return colors["anomaly"]
    if event.event == "ROW_INSERTED" or "ROW_INSERTED" in event.anomalies:
        return colors["inserted"]
    if event.changed_field == "amount" or "AMOUNT_REVISION" in event.anomalies or "KYLO_POSTED_VARIANCE" in event.anomalies:
        return colors["amount_changed"]
    if event.changed_field == "source":
        return colors["source_changed"]
    if event.changed_field == "date" or "DATE_INVERSION" in event.anomalies:
        return colors["date_changed"]
    if event.event == "ANOMALY":
        return colors["anomaly"]
    if event.event == "ROW_REMOVED":
        return colors["removed"]
    return colors["default"]


def _build_sheet_title_to_id(meta: Dict[str, object]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for sh in meta.get("sheets", []) or []:
        props = (sh or {}).get("properties") or {}
        sid = props.get("sheetId")
        title = props.get("title")
        if sid is None or not isinstance(title, str) or not title.strip():
            continue
        k = _norm_tab_key(title)
        if k not in out:
            out[k] = int(sid)
    return out


def _cfg_get(cfg: Any, dotted: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if hasattr(cfg, "get"):
        try:
            v = cfg.get(dotted, None)
            if v is not None:
                return v
        except TypeError:
            pass
    return default


def _repeat_cell_requests(
    spreadsheet_id: str,
    service,
    cells: List[Tuple[str, str, Dict[str, float]]],
    *,
    end_col: int,
) -> List[dict]:
    """cells: list of (tab, a1_cell_or_row0, color) — row0 int means full row highlight."""
    meta = google_api_execute(
        service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"),
        label="audit:sheet_meta",
    )
    title_map = _build_sheet_title_to_id(meta)
    requests: List[dict] = []
    for tab, loc, color in cells:
        sheet_id = title_map.get(_norm_tab_key(tab))
        if sheet_id is None:
            continue
        if isinstance(loc, int):
            row0, col_start, col_end = loc, 0, end_col
        else:
            m = re.match(r"^([A-Z]+)(\d+)$", str(loc).upper())
            if not m:
                continue
            col_letters, row_s = m.group(1), m.group(2)
            col_idx = 0
            for ch in col_letters:
                col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
            col_idx -= 1
            row0 = int(row_s) - 1
            col_start, col_end = col_idx, col_idx + 1
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": row0,
                        "endRowIndex": row0 + 1,
                        "startColumnIndex": col_start,
                        "endColumnIndex": col_end,
                    },
                    "cell": {"userEnteredFormat": {"backgroundColor": color}},
                    "fields": "userEnteredFormat.backgroundColor",
                }
            }
        )
    return requests


def apply_audit_highlights(
    service,
    events: List[ChangeEvent],
    cfg: Any,
    *,
    highlight_end_col: int = 7,
) -> int:
    import os

    raw_off = (os.environ.get("KYLO_AUDIT_HIGHLIGHTS") or "").strip().lower()
    if raw_off in ("0", "false", "no", "n", "off"):
        return 0
    block = _cfg_get(cfg, "audit.highlights") or {}
    if not isinstance(block, dict) or not bool(block.get("enabled", True)):
        return 0
    if not events:
        return 0

    colors = {
        "inserted": _rgb_from_cfg(block, "inserted_rgb", (1.0, 0.75, 0.75)),
        "amount_changed": _rgb_from_cfg(block, "amount_changed_rgb", (1.0, 0.85, 0.55)),
        "source_changed": _rgb_from_cfg(block, "source_changed_rgb", (1.0, 1.0, 0.65)),
        "date_changed": _rgb_from_cfg(block, "date_changed_rgb", (0.85, 0.75, 1.0)),
        "anomaly": _rgb_from_cfg(block, "anomaly_rgb", (1.0, 0.45, 0.45)),
        "removed": _rgb_from_cfg(block, "removed_rgb", (0.85, 0.85, 0.85)),
        "default": _rgb_from_cfg(block, "default_rgb", (0.95, 0.90, 0.80)),
    }

    by_sid: Dict[str, Dict[Tuple[str, int], Dict[str, float]]] = {}
    for ev in events:
        if ev.event in {"ROW_REMOVED", "ROW_SHIFTED"}:
            continue
        sid = ev.source_spreadsheet_id
        row0 = ev.sheet_row - 1
        color = _color_for_event(ev, colors)
        by_sid.setdefault(sid, {})[(ev.source_tab, row0)] = color

    total = 0
    end_col = max(1, int(block.get("end_column", highlight_end_col)))
    for spreadsheet_id, rows in by_sid.items():
        cells = [(tab, row0, color) for (tab, row0), color in rows.items()]
        requests = []
        try:
            meta = google_api_execute(
                service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"),
                label="audit:sheet_meta",
            )
            title_map = _build_sheet_title_to_id(meta)
            for tab, row0, color in sorted(cells, key=lambda x: (_norm_tab_key(x[0]), x[1])):
                sheet_id = title_map.get(_norm_tab_key(tab))
                if sheet_id is None:
                    continue
                requests.append(
                    {
                        "repeatCell": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": int(row0),
                                "endRowIndex": int(row0) + 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": end_col,
                            },
                            "cell": {"userEnteredFormat": {"backgroundColor": color}},
                            "fields": "userEnteredFormat.backgroundColor",
                        }
                    }
                )
        except Exception as e:
            print(f"[AUDIT] WARN: could not load sheet meta: {e}")
            continue
        chunk = 100
        for i in range(0, len(requests), chunk):
            batch = requests[i : i + chunk]
            try:
                google_api_execute(
                    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": batch}),
                    label="audit:repeatCell_highlights",
                )
                total += len(batch)
            except Exception as e:
                print(f"[AUDIT] WARN: highlight batchUpdate failed: {e}")
    if total:
        print(f"[AUDIT] Applied audit highlights to {total} row range(s)")
    return total


def apply_target_cell_highlights(
    service,
    spreadsheet_id: str,
    flagged_ranges: List[str],
    cfg: Any,
) -> int:
    """Red-tint target workbook cells that were written despite audit flags."""
    if not flagged_ranges or not spreadsheet_id:
        return 0
    block = _cfg_get(cfg, "posting.flagged_target_highlight") or {}
    if isinstance(block, dict) and block.get("enabled") is False:
        return 0
    rgb = block.get("rgb") if isinstance(block, dict) else None
    if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
        color = {"red": float(rgb[0]), "green": float(rgb[1]), "blue": float(rgb[2])}
    else:
        color = {"red": 1.0, "green": 0.45, "blue": 0.45}

    by_tab: Dict[str, List[str]] = {}
    for a1 in flagged_ranges:
        if "!" not in a1:
            continue
        tab, cell = a1.split("!", 1)
        tab = tab.strip("'")
        by_tab.setdefault(tab, []).append(cell)

    total = 0
    for tab, cells in by_tab.items():
        cell_specs = [(tab, c, color) for c in cells]
        try:
            requests = _repeat_cell_requests(spreadsheet_id, service, cell_specs, end_col=1)
            if requests:
                google_api_execute(
                    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}),
                    label="audit:target_flagged_highlight",
                )
                total += len(requests)
        except Exception as e:
            print(f"[AUDIT] WARN: target highlight failed: {e}")
    if total:
        print(f"[AUDIT] Flagged {total} target cell(s) red")
    return total


def clear_row_highlights(
    service,
    spreadsheet_id: str,
    tab: str,
    row_numbers: List[int],
    cfg: Any,
    *,
    highlight_end_col: int = 7,
) -> int:
    if not row_numbers:
        return 0
    white = {"red": 1.0, "green": 1.0, "blue": 1.0}
    block = _cfg_get(cfg, "audit.highlights") or {}
    end_col = max(1, int(block.get("end_column", highlight_end_col))) if isinstance(block, dict) else highlight_end_col
    try:
        meta = google_api_execute(
            service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))"),
            label="audit:sheet_meta_clear",
        )
    except Exception:
        return 0
    title_map = _build_sheet_title_to_id(meta)
    sheet_id = title_map.get(_norm_tab_key(tab))
    if sheet_id is None:
        return 0
    requests = [
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": int(row) - 1,
                    "endRowIndex": int(row),
                    "startColumnIndex": 0,
                    "endColumnIndex": end_col,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": white}},
                "fields": "userEnteredFormat.backgroundColor",
            }
        }
        for row in sorted(set(row_numbers))
        if row > 0
    ]
    if not requests:
        return 0
    try:
        google_api_execute(
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}),
            label="audit:clear_highlights",
        )
        return len(requests)
    except Exception:
        return 0


__all__ = ["apply_audit_highlights", "apply_target_cell_highlights", "clear_row_highlights"]
