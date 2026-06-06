#!/usr/bin/env python3
"""
sheet_label_pipeline.py — Bank Vendor Cleaner (deterministic Google Sheets pipeline).

Reads source column C, writes plain-text cleaned labels (C) and City/State (D).
Default: DRY_RUN=true. Live writes require --no-dry-run and --approved.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

AI_LAB_ROOT = Path(__file__).resolve().parents[1]
if str(AI_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_LAB_ROOT))

from brain.bank_vendor_cleaner.engine import (
    assert_plain_values,
    build_alias_lookup,
    get_label_with_source,
    process_rows,
)
from brain.bank_vendor_cleaner.loader import (
    load_alias_map,
    load_cleaning_rules,
    load_manifest,
    resolve_config_path,
)
from brain.bank_vendor_cleaner.paths import default_alias_map_path, reports_dir


@dataclass
class PipelineConfig:
    spreadsheet_id: str
    source_sheet_name: str
    dest_sheet_name: str
    start_row: int = 2
    source_column: str = "C"
    label_output_column: str = "C"
    location_output_column: str = "D"
    dry_run: bool = True
    approval_required: bool = True
    approved: bool = False
    replace_formulas: bool = False
    alias_map_path: Path | None = None
    cleaning_rules_path: Path | None = None
    report_dir: Path | None = None
    vendor_lookup: bool = False


def _env_bool(name: str, default: bool) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def load_pipeline_config(args: argparse.Namespace) -> PipelineConfig:
    manifest = load_manifest()
    scope = manifest.get("single_sheet_scope") or {}
    spreadsheet_id = (
        args.spreadsheet_id
        or os.environ.get("SPREADSHEET_ID")
        or scope.get("spreadsheet_id")
        or ""
    ).strip()
    alias_env = os.environ.get("ALIAS_MAP_PATH")
    rules_env = os.environ.get("CLEANING_RULES_PATH")
    report_env = os.environ.get("REPORT_DIR")
    return PipelineConfig(
        spreadsheet_id=spreadsheet_id,
        source_sheet_name=(
            args.source_sheet_name
            or os.environ.get("SOURCE_SHEET_NAME")
            or scope.get("source_tab_name")
            or "transaction tab sheet"
        ),
        dest_sheet_name=(
            args.dest_sheet_name
            or os.environ.get("DEST_SHEET_NAME")
            or scope.get("destination_tab_name")
            or "CLEANED TRANSACTIONS-TAB SHEET"
        ),
        start_row=int(args.start_row or os.environ.get("START_ROW") or 2),
        source_column=os.environ.get("SOURCE_COLUMN", "C"),
        label_output_column=os.environ.get("LABEL_OUTPUT_COLUMN", "C"),
        location_output_column=os.environ.get("LOCATION_OUTPUT_COLUMN", "D"),
        dry_run=args.dry_run if args.dry_run is not None else _env_bool("DRY_RUN", True),
        approval_required=_env_bool("APPROVAL_REQUIRED", True),
        approved=bool(args.approved),
        replace_formulas=bool(args.replace_formulas) or _env_bool("REPLACE_FORMULAS", False),
        alias_map_path=resolve_config_path(
            args.alias_map_path or alias_env or str(default_alias_map_path())
        ),
        cleaning_rules_path=resolve_config_path(rules_env) if rules_env else None,
        report_dir=resolve_config_path(report_env) if report_env else reports_dir(),
    )


def validate_scope(config: PipelineConfig) -> None:
    manifest = load_manifest()
    allowed_id = (
        os.environ.get("ALLOWED_SPREADSHEET_ID")
        or (manifest.get("single_sheet_scope") or {}).get("spreadsheet_id")
        or config.spreadsheet_id
    )
    if config.spreadsheet_id != allowed_id:
        raise SystemExit("Abort: wrong spreadsheet id")
    allowed_source = os.environ.get("ALLOWED_SOURCE_SHEET_NAME") or config.source_sheet_name
    allowed_dest = os.environ.get("ALLOWED_DEST_SHEET_NAME") or config.dest_sheet_name
    if config.source_sheet_name != allowed_source:
        raise SystemExit("Abort: wrong source sheet")
    if config.dest_sheet_name != allowed_dest:
        raise SystemExit("Abort: wrong destination sheet")


def _run_vendor_lookup_pass(
    source_values: list[str],
    processed: list,
    alias_map: dict,
    cleaning_rules: dict,
    *,
    write_pending: bool,
) -> list[dict]:
    from brain.bank_vendor_cleaner.vendor_lookup import lookup_vendor, should_trigger_lookup

    alias_by_raw, _ = build_alias_lookup(alias_map)
    results: list[dict] = []
    for raw, proc in zip(source_values, processed):
        label, source = get_label_with_source(raw, alias_by_raw, cleaning_rules=cleaning_rules)
        if not should_trigger_lookup(raw, label, source):
            continue
        lr = lookup_vendor(
            raw,
            deterministic_label=proc.label,
            deterministic_location=proc.location,
            label_source=source,
            write_pending=write_pending,
        )
        results.append(lr.to_dict())
    return results


def run_pipeline(config: PipelineConfig) -> dict:
    validate_scope(config)
    if not config.dry_run and config.approval_required and not config.approved:
        raise SystemExit("Abort: write approval required (--approved)")

    alias_map = load_alias_map(config.alias_map_path)
    cleaning_rules = load_cleaning_rules(config.cleaning_rules_path)

    from lib.google_sheets_client import (
        detect_formula_cells_in_range,
        get_sheets_service,
        read_column_values,
        write_column_values,
    )

    service = get_sheets_service()
    source_values = read_column_values(
        service,
        config.spreadsheet_id,
        config.source_sheet_name,
        config.source_column,
        config.start_row,
    )
    processed, last_row = process_rows(
        source_values,
        config.start_row,
        alias_map,
        cleaning_rules=cleaning_rules,
    )
    labels = [r.label for r in processed]
    locations = [r.location for r in processed]
    assert_plain_values(labels)
    assert_plain_values(locations)

    warnings: list[str] = []
    errors: list[str] = []

    if processed:
        end_row = config.start_row + len(processed) - 1
        dest_range = (
            f"{config.label_output_column}{config.start_row}:"
            f"{config.location_output_column}{end_row}"
        )
        if not config.replace_formulas:
            formula_cells = detect_formula_cells_in_range(
                service,
                config.spreadsheet_id,
                config.dest_sheet_name,
                dest_range,
            )
            if formula_cells:
                msg = f"Destination contains formulas at: {', '.join(formula_cells[:5])}"
                if len(formula_cells) > 5:
                    msg += f" (+{len(formula_cells) - 5} more)"
                if config.dry_run:
                    warnings.append(msg)
                else:
                    raise SystemExit(f"Abort: {msg} (use --replace-formulas to override)")

    rows_written_c = 0
    rows_written_d = 0
    if processed and not config.dry_run:
        rows_written_c = write_column_values(
            service,
            config.spreadsheet_id,
            config.dest_sheet_name,
            config.label_output_column,
            config.start_row,
            labels,
        )
        rows_written_d = write_column_values(
            service,
            config.spreadsheet_id,
            config.dest_sheet_name,
            config.location_output_column,
            config.start_row,
            locations,
        )
    elif processed and config.dry_run:
        preview = [
            {"row": config.start_row + i, "label": labels[i], "location": locations[i]}
            for i in range(min(5, len(labels)))
        ]
        print(json.dumps({"dry_run_preview": preview, "total_rows": len(labels)}, indent=2))

    vendor_lookup_results: list[dict] = []
    if config.vendor_lookup and processed:
        active = source_values[: len(processed)]
        vendor_lookup_results = _run_vendor_lookup_pass(
            active,
            processed,
            alias_map,
            cleaning_rules,
            write_pending=not config.dry_run,
        )

    report = {
        "spreadsheet_id": config.spreadsheet_id,
        "source_tab": config.source_sheet_name,
        "destination_tab": config.dest_sheet_name,
        "rows_scanned": len(source_values),
        "rows_processed": len(processed),
        "rows_written_c": rows_written_c,
        "rows_written_d": rows_written_d,
        "last_source_row": last_row,
        "last_written_row": last_row if processed else config.start_row - 1,
        "dry_run": config.dry_run,
        "vendor_lookup_count": len(vendor_lookup_results),
        "vendor_lookup": vendor_lookup_results,
        "warnings": warnings,
        "errors": errors,
    }
    out_dir = config.report_dir or reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "bank_vendor_cleaner_run_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Bank vendor cleaner Google Sheets pipeline")
    parser.add_argument("--spreadsheet-id", default=None)
    parser.add_argument("--source-sheet-name", default=None)
    parser.add_argument("--dest-sheet-name", default=None)
    parser.add_argument("--start-row", type=int, default=None)
    parser.add_argument("--alias-map-path", default=None)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=None)
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false")
    parser.add_argument("--approved", action="store_true", default=False)
    parser.add_argument("--replace-formulas", action="store_true", default=False)
    parser.add_argument("--vendor-lookup", action="store_true", default=False)
    args = parser.parse_args()

    if args.dry_run is None:
        args.dry_run = _env_bool("DRY_RUN", True)

    config = load_pipeline_config(args)
    config.vendor_lookup = bool(args.vendor_lookup) or _env_bool("VENDOR_LOOKUP_ENABLED", False)
    if not config.spreadsheet_id:
        raise SystemExit("Missing spreadsheet id (--spreadsheet-id or SPREADSHEET_ID)")

    run_pipeline(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
