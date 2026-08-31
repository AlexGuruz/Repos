"""Operator Desk Growflow tools — safety + catalog."""
from __future__ import annotations

import json
from pathlib import Path

from operator_desk.tools import growflow_ops


def test_catalog_resolves():
    result = growflow_ops.get_growflow_catalog()
    assert result.ok is True
    surfaces = result.metrics.get("surfaces") or []
    ids = {s.get("surface_id") for s in surfaces}
    assert "retail_dashboard" in ids
    assert "read_surfaces_catalog" in ids


def test_snapshot_rejects_metrics_md_as_sales(tmp_path, monkeypatch):
    snap = {
        "generated_at": "2026-07-14T12:00:00Z",
        "stale": False,
        "summary_short": "bad",
        "data": {
            "latest_sales_summary": "# Metric Definitions and Formulas\n\n## Confidence labels",
            "known_blockers": [],
        },
    }
    path = tmp_path / "growflow_snapshot.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    monkeypatch.setattr(growflow_ops.pathmod, "growflow_snapshot_path", lambda: path)
    result = growflow_ops.get_growflow_status(prefer_prepared_snapshot=True)
    assert result.ok is False
    assert any("formula_docs" in b for b in result.known_blockers) or result.degraded


def test_growflow_ops_module_has_no_refresh_symbol():
    src = Path(growflow_ops.__file__).read_text(encoding="utf-8")
    assert "POST" not in src or "/refresh" not in src
    assert "retail/refresh" not in src
