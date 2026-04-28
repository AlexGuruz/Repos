"""
Heuristic classification for Growflow automation entrypoints (Phase 3).

Used by tests and scripts/generate_growflow_runners_json.py — not used at chat runtime.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# README-aligned repeatable runners (scripts/ + selected repo-root modules).
CANONICAL_RUNNER_NAMES = frozenset(
    {
        "allocate_stock_pool_by_brand.py",
        "allocate_brand_pool_merit.py",
        "build_projection_by_category_brand.py",
        "build_projection_dashboard_google_sheet.py",
        "build_transfer_receipts_db.py",
        "build_trip_sheet_google_doc.py",
        "cartel_7pk_portfolio_projection.py",
        "complete_18k_projection.py",
        "export_brand_suppliers_to_sheet.py",
        "export_projection_dashboard_layout.py",
        "export_top15_mj_brands_30d_windows.py",
        "export_transfer_receipt_units.py",
        "introspect_growflow_schema.py",
        "list_projection_dashboard_charts.py",
        "projection_dashboard_to_sheet.py",
        "rank_mj_brands_profit_velocity_sheet.py",
        "restore_dashboard_charts_from_layout_snapshot.py",
        "run_growflow_discovery_queries.py",
        "snapshot_dashboard_chart_layout.py",
        "supplier_sales_pace_by_category.py",
        "transfer_sellout_by_brand_category.py",
        "verify_projection_dashboard_sheet.py",
    }
)

# Script outputs that feed ai-lab `growflow_snapshot` (see brain/prepared_context/builders.py).
PREPARED_CONTEXT_FEEDER_NAMES = frozenset(
    {
        "build_transfer_receipts_db.py",
        "export_transfer_receipt_units.py",
        "export_top15_mj_brands_30d_windows.py",
        "build_projection_dashboard_google_sheet.py",
        "export_projection_dashboard_layout.py",
    }
)

READ_SAFE_TOOL_CANDIDATE_NAMES = frozenset(
    {
        "validate_projection_layer2_csv.py",
        "validate_cartel_7pk_projection.py",
    }
)

SCHEDULED_JOB_CANONICAL_NAMES = frozenset(
    {
        "build_projection_by_category_brand.py",
        "build_projection_dashboard_google_sheet.py",
        "rank_mj_brands_profit_velocity_sheet.py",
        "build_transfer_receipts_db.py",
        "export_transfer_receipt_units.py",
        "export_top15_mj_brands_30d_windows.py",
        "export_projection_dashboard_layout.py",
        "introspect_growflow_schema.py",
    }
)

DEPRECATED_ARCHIVE_NAMES = frozenset(
    {
        "_patch_ac10.py",
        "_patch_iferror_test.py",
        "_sellout_final.py",
        "_fix_arctic_line.py",
    }
)

# Do not register in ai-lab tool registry without full approval metadata (writes / APIs / Sheets).
UNSAFE_WITHOUT_METADATA_NAMES = frozenset(
    {
        "ingest_growflow_to_db.py",
        "build_projection_dashboard_google_sheet.py",
        "build_transfer_receipts_db.py",
        "projection_dashboard_to_sheet.py",
        "build_trip_sheet_google_doc.py",
        "all_categories_inventory_and_daily_rebuild.py",
    }
)

_EXPLICIT_CATEGORY: dict[str, str] = {
    "monthly_gross_projection_to_sheet.py": "scheduled_job_candidate",
    "inventory_sales_monitor.py": "scheduled_job_candidate",
    "inventory_vs_sales_last_6_months.py": "manual_diagnostic",
    "all_categories_inventory_and_daily_rebuild.py": "unsafe_without_approval_metadata",
    "company_bi/scripts/monthly_run.py": "scheduled_job_candidate",
    "company_bi/scripts/payroll_last_period.py": "scheduled_job_candidate",
    "company_bi/scripts/recurring_bills_summary.py": "scheduled_job_candidate",
    "company_bi/scripts/audit_other_expenses.py": "read_safe_tool_candidate",
    "company_bi/scripts/ingest_growflow_to_db.py": "unsafe_without_approval_metadata",
    "company_bi/scripts/suggest_category_rules.py": "manual_diagnostic",
    "company_bi/scripts/list_uncategorized_and_review.py": "manual_diagnostic",
    "company_bi/scripts/list_rent_matches.py": "manual_diagnostic",
}


def _basename(rel: str) -> str:
    return Path(rel.replace("\\", "/")).name


def _approval_required_flag(category: str, name: str) -> bool:
    if category in ("unsafe_without_approval_metadata", "deprecated_archive_later"):
        return True
    if name in UNSAFE_WITHOUT_METADATA_NAMES:
        return True
    if category == "canonical_runner" and name in UNSAFE_WITHOUT_METADATA_NAMES:
        return True
    return False


def classify_growflow_entry(relative_path: str) -> dict[str, Any]:
    rel = relative_path.replace("\\", "/").lstrip("/")
    name = _basename(rel)

    if rel in _EXPLICIT_CATEGORY:
        cat = _EXPLICIT_CATEGORY[rel]
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": cat,
            "notes": "explicit classification",
            "approval_required_for_tool_registry": _approval_required_flag(cat, name),
            "prepared_context_source": name in PREPARED_CONTEXT_FEEDER_NAMES,
        }

    if name == "__init__.py":
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "manual_diagnostic",
            "notes": "package namespace marker only; not an execution entrypoint",
            "approval_required_for_tool_registry": False,
            "prepared_context_source": False,
        }

    if name in DEPRECATED_ARCHIVE_NAMES or (name.startswith("_patch") and name.endswith(".py")):
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "deprecated_archive_later",
            "notes": "legacy patch / one-off",
            "approval_required_for_tool_registry": True,
            "prepared_context_source": False,
        }

    probe_prefixes = ("_probe", "_tmp", "_dump", "_scan", "_check", "_print", "_query_", "_cartel_", "_sales_", "_weekday", "_last_", "_find_", "_orderitem", "_test")
    if name.startswith(probe_prefixes) or (name.startswith("_") and name.endswith(".py")):
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "manual_diagnostic",
            "notes": "underscore / probe / ad-hoc analysis",
            "approval_required_for_tool_registry": True,
            "prepared_context_source": False,
        }

    if name in ("probe_orderitems_field_batches.py", "probe_growflow_discovery_entities.py"):
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "manual_diagnostic",
            "notes": "probe script",
            "approval_required_for_tool_registry": False,
            "prepared_context_source": False,
        }

    low = name.lower()
    if any(x in low for x in ("worst_recovery", "efficiency_distribution", "top_allocation", "diag_vape", "query_sap")):
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "manual_diagnostic",
            "notes": "diagnostic / report script",
            "approval_required_for_tool_registry": False,
            "prepared_context_source": False,
        }

    if name in CANONICAL_RUNNER_NAMES:
        cat = "scheduled_job_candidate" if name in SCHEDULED_JOB_CANONICAL_NAMES else "canonical_runner"
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": cat,
            "notes": "primary pipeline / exports",
            "approval_required_for_tool_registry": _approval_required_flag(cat, name),
            "prepared_context_source": name in PREPARED_CONTEXT_FEEDER_NAMES,
        }

    if name in READ_SAFE_TOOL_CANDIDATE_NAMES:
        return {
            "path": f"Growflow/{rel}",
            "relative": rel,
            "category": "read_safe_tool_candidate",
            "notes": "read-biased; confirm side effects before tool registry",
            "approval_required_for_tool_registry": False,
            "prepared_context_source": name in PREPARED_CONTEXT_FEEDER_NAMES,
        }

    return {
        "path": f"Growflow/{rel}",
        "relative": rel,
        "category": "unknown_needs_review",
        "notes": "default — assign owner and category",
        "approval_required_for_tool_registry": False,
        "prepared_context_source": False,
    }


def discover_growflow_script_paths(growflow_root: Path) -> list[str]:
    out: list[str] = []
    scripts = growflow_root / "scripts"
    if scripts.is_dir():
        for p in sorted(scripts.glob("*.py")):
            out.append(f"scripts/{p.name}")
    bi = growflow_root / "company_bi" / "scripts"
    if bi.is_dir():
        for p in sorted(bi.glob("*.py")):
            out.append(f"company_bi/scripts/{p.name}")
    for pat in ("allocate_*.py", "inventory*.py", "monthly*.py", "all_categories*.py"):
        for p in growflow_root.glob(pat):
            if p.is_file() and p.suffix == ".py":
                out.append(p.name)
    return sorted(set(out))


def build_inventory(growflow_root: Path) -> dict[str, Any]:
    from datetime import datetime, timezone

    rows = [classify_growflow_entry(rel) for rel in discover_growflow_script_paths(growflow_root)]
    labels = [
        "canonical_runner",
        "read_safe_tool_candidate",
        "scheduled_job_candidate",
        "manual_diagnostic",
        "deprecated_archive_later",
        "unsafe_without_approval_metadata",
        "unknown_needs_review",
    ]
    counts = {lab: sum(1 for r in rows if r.get("category") == lab) for lab in labels}
    counts["prepared_context_feeders"] = sum(1 for r in rows if r.get("prepared_context_source"))
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "growflow_root": str(growflow_root.resolve()),
        "classification_labels": labels,
        "counts": counts,
        "scripts": rows,
    }
