"""Capital scenario approval gate (Growflow backend logic)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from dashboard.backend.main import (
    CapitalScenarioRequest,
    DEFAULT_CAPITAL_JSON,
    _jobs,
    _jobs_lock,
    _pending_capital,
    _pending_capital_lock,
    capital_scenario,
    deny_capital_scenario,
    execute_capital_scenario,
    job_status,
)


def _clear_state() -> None:
    with _pending_capital_lock:
        _pending_capital.clear()
    with _jobs_lock:
        _jobs.clear()


def test_capital_scenario_awaiting_approval():
    _clear_state()
    req = CapitalScenarioRequest(
        pool_usd=18000,
        velocity_days=49,
        cash_cycle_days=14,
        allocation_mode="buy-plan",
        skip_approval=False,
    )
    body = capital_scenario(req)
    assert body["status"] == "awaiting_approval"
    assert body["approval_required"] is True
    assert body["approval_id"].startswith("APR-cap-")
    assert body["job_id"]
    assert body["summary"]["pool_usd"] == 18000
    assert body["expected_output"] == "data/retail_capital_latest.json"
    with _pending_capital_lock:
        assert body["approval_id"] in _pending_capital


def test_capital_scenario_deny_discards_pending():
    _clear_state()
    req = CapitalScenarioRequest(pool_usd=20000, skip_approval=False)
    body = capital_scenario(req)
    aid = body["approval_id"]
    job_id = body["job_id"]
    before = DEFAULT_CAPITAL_JSON.read_text(encoding="utf-8") if DEFAULT_CAPITAL_JSON.is_file() else None
    result = deny_capital_scenario(aid)
    assert result["resolution"] == "denied"
    with _pending_capital_lock:
        assert aid not in _pending_capital
    with _jobs_lock:
        assert _jobs[job_id]["status"] == "denied"
    if before is not None:
        after = DEFAULT_CAPITAL_JSON.read_text(encoding="utf-8")
        assert after == before


def test_execute_reuses_pending_job_id():
    _clear_state()
    body = capital_scenario(CapitalScenarioRequest(pool_usd=15000, skip_approval=False))
    aid = body["approval_id"]
    job_id = body["job_id"]

    with patch("dashboard.backend.main._run_capital_scenario_job"):
        result = execute_capital_scenario(aid)

    assert result["job_id"] == job_id
    assert result["resolution"] == "approved"
    assert result["status"] == "queued"
    with _pending_capital_lock:
        assert aid not in _pending_capital
    with _jobs_lock:
        assert _jobs[job_id]["status"] == "queued"


def test_execute_unknown_approval_404():
    _clear_state()
    with pytest.raises(HTTPException) as exc:
        execute_capital_scenario("APR-cap-missing")
    assert exc.value.status_code == 404


def test_deny_unknown_approval_404():
    _clear_state()
    with pytest.raises(HTTPException) as exc:
        deny_capital_scenario("APR-cap-missing")
    assert exc.value.status_code == 404


def test_approve_starts_job_without_mutating_capital_json_immediately():
    _clear_state()
    before = DEFAULT_CAPITAL_JSON.read_text(encoding="utf-8") if DEFAULT_CAPITAL_JSON.is_file() else None

    body = capital_scenario(CapitalScenarioRequest(pool_usd=22000, skip_approval=False))

    with patch("dashboard.backend.main._run_capital_scenario_job"):
        execute_capital_scenario(body["approval_id"])

    if before is not None:
        assert DEFAULT_CAPITAL_JSON.read_text(encoding="utf-8") == before
    with _jobs_lock:
        assert _jobs[body["job_id"]]["status"] == "queued"


def test_job_status_after_approval():
    _clear_state()
    body = capital_scenario(CapitalScenarioRequest(skip_approval=False))
    with patch("dashboard.backend.main._run_capital_scenario_job"):
        execute_capital_scenario(body["approval_id"])
    status = job_status(body["job_id"])
    assert status["job_id"] == body["job_id"]
    assert status["status"] in ("queued", "running_projection", "building_capital", "completed")
