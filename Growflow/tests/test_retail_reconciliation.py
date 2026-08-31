"""Tests for retail dashboard reconciliation gate."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lib.retail_dashboard.reconcile import (
    Tolerance,
    exit_code_for_report,
    load_dashboard_json,
    load_reconciliation_report,
    load_reference_csv,
    load_reference_json,
    reconcile,
    reconciliation_status_summary,
    run_sum_gate_checks,
    within_tolerance,
    write_report,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "retail_dashboard"
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def golden_dashboard() -> dict:
    return json.loads((FIXTURES / "dashboard_golden.json").read_text(encoding="utf-8"))


def test_within_tolerance_money():
    tol = Tolerance(money_abs=1.0, pct=0.005)
    assert within_tolerance(100.0, 100.5, tol)
    assert not within_tolerance(100.0, 102.0, tol)


def test_within_tolerance_pct():
    tol = Tolerance(money_abs=1.0, pct=0.005)
    assert within_tolerance(10000.0, 10040.0, tol)  # 0.4% within 0.5%
    assert not within_tolerance(10000.0, 10100.0, tol)  # 1%


def test_sum_gate_checks_pass(golden_dashboard):
    from lib.retail_dashboard.reconcile import _extract_actual

    actual = _extract_actual(golden_dashboard)
    checks = run_sum_gate_checks(actual, Tolerance())
    assert all(c["status"] == "pass" for c in checks)
    assert len(checks) == 3


def test_reconcile_pass_csv_reference(golden_dashboard):
    ref = load_reference_csv(FIXTURES / "reference_golden.csv")
    report = reconcile(
        golden_dashboard,
        reference=ref,
        reference_type="csv",
        reference_path=FIXTURES / "reference_golden.csv",
    )
    assert report["status"] == "pass"
    assert report["summary"]["checks_failed"] == 0
    assert report["summary"]["checks_total"] >= 10
    assert exit_code_for_report(report) == 0


def test_reconcile_pass_json_reference(golden_dashboard):
    ref = load_reference_json(FIXTURES / "reference_golden.json")
    report = reconcile(
        golden_dashboard,
        reference=ref,
        reference_type="json",
        reference_path=FIXTURES / "reference_golden.json",
    )
    assert report["status"] == "pass"
    assert exit_code_for_report(report) == 0


def test_reconcile_fail_when_reference_exceeds_tolerance(golden_dashboard):
    ref = load_reference_csv(FIXTURES / "reference_mismatch.csv")
    report = reconcile(golden_dashboard, reference=ref, reference_type="csv")
    assert report["status"] == "fail"
    failed = [c for c in report["checks"] if c["status"] == "fail"]
    assert any(c["name"] == "ref_store_net_sales" for c in failed)
    assert exit_code_for_report(report) == 1


def test_reconcile_sum_gates_only_without_reference(golden_dashboard):
    report = reconcile(golden_dashboard)
    assert report["status"] == "pass"
    assert report["summary"]["checks_total"] == 3
    assert all(c["name"].startswith("sum_gate_") for c in report["checks"])


def test_reference_csv_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        load_reference_csv(bad)


def test_dashboard_json_missing_meta(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="missing meta"):
        load_dashboard_json(p)


def test_write_report_roundtrip(tmp_path, golden_dashboard):
    out = tmp_path / "report.json"
    report = reconcile(golden_dashboard)
    write_report(report, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["status"] == "pass"
    assert "checks" in loaded
    assert loaded["tolerance"]["money_abs"] == 1.0


def test_cli_pass(tmp_path, monkeypatch):
    from scripts.reconcile_retail_dashboard import main

    out = tmp_path / "reconciliation.json"
    monkeypatch.chdir(REPO)
    os.environ["PYTHONPATH"] = str(REPO)
    code = main([
        "--dashboard-json",
        str(FIXTURES / "dashboard_golden.json"),
        "--reference-csv",
        str(FIXTURES / "reference_golden.csv"),
        "--out",
        str(out),
    ])
    assert code == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "pass"


def test_cli_fail(tmp_path, monkeypatch):
    from scripts.reconcile_retail_dashboard import main

    out = tmp_path / "reconciliation.json"
    monkeypatch.chdir(REPO)
    code = main([
        "--dashboard-json",
        str(FIXTURES / "dashboard_golden.json"),
        "--reference-csv",
        str(FIXTURES / "reference_mismatch.csv"),
        "--out",
        str(out),
    ])
    assert code == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["status"] == "fail"


def test_cli_invalid_dashboard(tmp_path, monkeypatch):
    from scripts.reconcile_retail_dashboard import main

    missing = tmp_path / "missing.json"
    monkeypatch.chdir(REPO)
    code = main(["--dashboard-json", str(missing)])
    assert code == 2


def test_reconciliation_status_summary_missing():
    summary = reconciliation_status_summary(None)
    assert summary["status"] == "missing"
    assert "message" in summary


def test_reconciliation_status_summary_fail(golden_dashboard):
    ref = load_reference_csv(FIXTURES / "reference_mismatch.csv")
    report = reconcile(golden_dashboard, reference=ref, reference_type="csv")
    summary = reconciliation_status_summary(report)
    assert summary["status"] == "fail"
    assert len(summary["failed_checks"]) >= 1


def test_load_reconciliation_report_roundtrip(tmp_path, golden_dashboard):
    out = tmp_path / "report.json"
    write_report(reconcile(golden_dashboard), out)
    loaded = load_reconciliation_report(out)
    assert loaded is not None
    assert loaded["status"] == "pass"


def test_reconciliation_api_endpoint(tmp_path, monkeypatch):
    from dashboard.backend import main as api_main

    report = reconcile(json.loads((FIXTURES / "dashboard_golden.json").read_text(encoding="utf-8")))
    report_path = tmp_path / "retail_reconciliation_latest.json"
    write_report(report, report_path)
    monkeypatch.setattr(api_main, "DEFAULT_REPORT_JSON", report_path)

    result = api_main.get_reconciliation()
    assert result["status"] == "pass"
    assert result["generated_at"]


def test_exit_code_strict_warning(golden_dashboard):
    report = reconcile(golden_dashboard)
    report["status"] = "warning"
    assert exit_code_for_report(report, strict=False) == 0
    assert exit_code_for_report(report, strict=True) == 1


def test_release_gate_skip_build_reconcile_only(tmp_path, monkeypatch):
    from scripts.run_retail_release_gate import main as gate_main

    dash = tmp_path / "dashboard.json"
    dash.write_text((FIXTURES / "dashboard_golden.json").read_text(encoding="utf-8"), encoding="utf-8")
    ref = tmp_path / "ref.csv"
    ref.write_text((FIXTURES / "reference_golden.csv").read_text(encoding="utf-8"), encoding="utf-8")
    out = tmp_path / "recon.json"

    monkeypatch.chdir(REPO)
    code = gate_main([
        "--skip-build",
        "--dashboard-json",
        str(dash),
        "--reference-csv",
        str(ref),
        "--out",
        str(out),
    ])
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "pass"
