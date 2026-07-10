"""
Cross-run schema fingerprinting and drift detection for Growflow API responses.

Compares flattened field paths from sample rows against a saved baseline to detect
missing/renamed fields and new keys (possible schema expansion).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT_DIR = REPO_ROOT / "state" / "schema_fingerprints"


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def flatten_field_paths(obj: Any, prefix: str = "") -> set[str]:
    """
    Collect dot-paths for dict leaves and nested dicts.
    For lists of dicts, recurse into the first element with a [] segment (shape probe).
    """
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.add(key)
            if isinstance(v, dict):
                out |= flatten_field_paths(v, key)
            elif isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, dict):
                    list_key = f"{key}[]"
                    out.add(list_key)
                    out |= flatten_field_paths(first, list_key)
    return out


def fingerprint_from_rows(rows: list[dict[str, Any]], *, max_rows: int = 25) -> dict[str, Any]:
    paths: set[str] = set()
    for row in rows[: max(1, max_rows)]:
        paths |= flatten_field_paths(row)
    return {
        "field_paths": sorted(paths),
        "sample_row_count": min(len(rows), max_rows),
    }


def _norm_path(path: str) -> str:
    return str(path).replace("[]", ".")


def _path_matches_contract_field(path: str, field: str) -> bool:
    """True if flattened path corresponds to contract field (e.g. Product.Brand.Name)."""
    p = _norm_path(path)
    f = _norm_path(field)
    if p == f:
        return True
    if f in p and (p.endswith("." + f) or p.endswith(f)):
        return True
    return False


def compare_fingerprints(
    baseline_paths: set[str],
    current_paths: set[str],
    *,
    required_fields: list[str],
    optional_fields: list[str],
) -> dict[str, Any]:
    missing = sorted(baseline_paths - current_paths)
    added = sorted(current_paths - baseline_paths)

    critical_missing: list[str] = []
    for m in missing:
        for rf in required_fields:
            if _path_matches_contract_field(m, str(rf)):
                critical_missing.append(m)
                break

    unstable_new = [p for p in added if any(p.endswith(suf) for suf in ("Brand", "Supplier", "Packages"))]

    return {
        "missing_paths": missing,
        "added_paths": added,
        "critical_missing_paths": sorted(set(critical_missing)),
        "possibly_unstable_new_paths": unstable_new,
        "baseline_path_count": len(baseline_paths),
        "current_path_count": len(current_paths),
    }


def load_baseline_fingerprint(metric_id: str) -> set[str] | None:
    p = FINGERPRINT_DIR / f"{metric_id}.json"
    if not p.is_file():
        return None
    data = _as_dict(json.loads(p.read_text(encoding="utf-8")))
    fp = data.get("field_paths")
    if isinstance(fp, list):
        return set(str(x) for x in fp)
    return None


def save_baseline_fingerprint(metric_id: str, fingerprint: dict[str, Any]) -> Path:
    FINGERPRINT_DIR.mkdir(parents=True, exist_ok=True)
    path = FINGERPRINT_DIR / f"{metric_id}.json"
    path.write_text(json.dumps(fingerprint, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def verify_against_baseline(
    metric_id: str,
    rows: list[dict[str, Any]],
    *,
    required_fields: list[str],
    optional_fields: list[str],
    update_baseline: bool = False,
) -> dict[str, Any]:
    """
    Compare current row sample fingerprint to saved baseline.

    If no baseline exists, optionally seeds baseline when update_baseline=True.
    """
    current_fp = fingerprint_from_rows(rows)
    current_paths = set(current_fp["field_paths"])
    baseline = load_baseline_fingerprint(metric_id)

    if baseline is None:
        if update_baseline and current_paths:
            save_baseline_fingerprint(metric_id, current_fp)
        return {
            "baseline_exists": False,
            "drift": None,
            "baseline_updated": bool(update_baseline and current_paths),
            "schema_drift_warnings": [],
        }

    drift = compare_fingerprints(baseline, current_paths, required_fields=required_fields, optional_fields=optional_fields)
    warnings: list[str] = []
    if drift["critical_missing_paths"]:
        warnings.append(
            "schema_drift: required-shape paths missing vs baseline: "
            + ", ".join(drift["critical_missing_paths"][:12])
            + (" …" if len(drift["critical_missing_paths"]) > 12 else "")
        )
    if drift["missing_paths"] and not drift["critical_missing_paths"]:
        warnings.append(
            f"schema_drift: {len(drift['missing_paths'])} path(s) present in baseline but missing now (non-required)."
        )
    if drift["possibly_unstable_new_paths"]:
        warnings.append(
            "schema_drift: new paths flagged as potentially unstable: "
            + ", ".join(drift["possibly_unstable_new_paths"][:8])
        )

    if update_baseline:
        save_baseline_fingerprint(metric_id, current_fp)

    return {
        "baseline_exists": True,
        "drift": drift,
        "baseline_updated": bool(update_baseline),
        "schema_drift_warnings": warnings,
    }
