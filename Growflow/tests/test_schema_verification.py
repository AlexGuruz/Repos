from __future__ import annotations

from lib.schema_verification import (
    compare_fingerprints,
    fingerprint_from_rows,
    flatten_field_paths,
    save_baseline_fingerprint,
    verify_against_baseline,
)


def test_flatten_field_paths_nested():
    row = {"a": 1, "Product": {"Brand": {"Name": "X"}}, "Packages": [{"objectId": "p1", "Cost": 10}]}
    paths = flatten_field_paths(row)
    assert "Product.Brand.Name" in paths
    assert any("Packages" in p for p in paths)


def test_compare_fingerprints_detects_missing_required_shape():
    baseline = {"objectId", "SoldAt", "GrossPrice", "Product.Brand.Name"}
    current = {"objectId", "SoldAt", "GrossPrice"}
    drift = compare_fingerprints(
        baseline,
        current,
        required_fields=["Product.Brand.Name"],
        optional_fields=[],
    )
    assert "Product.Brand.Name" in drift["missing_paths"]
    assert any("Product.Brand.Name" in p for p in drift["critical_missing_paths"])


def test_verify_against_baseline_updates_when_requested(tmp_path, monkeypatch):
    from lib import schema_verification as sv

    monkeypatch.setattr(sv, "FINGERPRINT_DIR", tmp_path)
    rows = [{"objectId": "1", "SoldAt": "2026-01-01T00:00:00.000Z", "GrossPrice": 100}]
    first = verify_against_baseline(
        "test_metric",
        rows,
        required_fields=["objectId"],
        optional_fields=["SoldAt"],
        update_baseline=True,
    )
    assert first.get("baseline_updated") is True
    second = verify_against_baseline(
        "test_metric",
        rows,
        required_fields=["objectId"],
        optional_fields=["SoldAt"],
        update_baseline=False,
    )
    assert second.get("baseline_exists") is True
    assert second.get("schema_drift_warnings") == []


def test_verify_detects_drift_after_baseline(tmp_path, monkeypatch):
    from lib import schema_verification as sv

    monkeypatch.setattr(sv, "FINGERPRINT_DIR", tmp_path)
    rows_a = [{"objectId": "1", "SoldAt": "2026-01-01T00:00:00.000Z", "GrossPrice": 100, "LegacyField": 1}]
    verify_against_baseline(
        "drift_metric",
        rows_a,
        required_fields=["objectId", "LegacyField"],
        optional_fields=[],
        update_baseline=True,
    )
    rows_b = [{"objectId": "1", "SoldAt": "2026-01-01T00:00:00.000Z", "GrossPrice": 100}]
    out = verify_against_baseline(
        "drift_metric",
        rows_b,
        required_fields=["objectId", "LegacyField"],
        optional_fields=[],
        update_baseline=False,
    )
    assert out.get("baseline_exists") is True
    warnings = out.get("schema_drift_warnings") or []
    assert any("schema_drift" in w.lower() for w in warnings)


def test_fingerprint_from_rows_sample_limit():
    rows = [{"k": i} for i in range(30)]
    fp = fingerprint_from_rows(rows, max_rows=5)
    assert fp["sample_row_count"] == 5
