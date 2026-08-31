from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routers import workers
from services import worker_fleet


def test_resolve_aliases():
    assert worker_fleet.resolve_node_id("worker-rig-01") == "worker-node"
    assert worker_fleet.resolve_node_id("worker-rig-02") == "power-1"
    assert worker_fleet.resolve_node_id("power-1") == "power-1"
    assert worker_fleet.resolve_node_id("acheron") == "acheron"


def test_health_shape_uses_fleet_not_ollama_on_power1():
    fake = {
        "ok": True,
        "checked_at": "2026-01-01T00:00:00Z",
        "nodes": [
            {
                "id": "power-1",
                "display_name": "power-1",
                "role": "primary_worker",
                "notes": "No Ollama",
                "status": "degraded",
                "critical_ok": False,
                "worker_assistant_ok": False,
                "all_ok": False,
                "services": [
                    {"name": "worker_assistant", "ok": False, "url": "http://127.0.0.1:8765/health"},
                    {"name": "n8n", "ok": True, "url": "http://127.0.0.1:5678/"},
                ],
                "tunnel_status": {
                    "worker_name": "power-1",
                    "expected_ports": [8765, 5678],
                    "reachable_ports": [8765, 5678],
                    "missing_ports": [],
                    "likely_up": True,
                    "detail": "Tunnel ports reachable.",
                },
            }
        ],
        "summary": {"power-1": "degraded"},
    }
    with patch.object(worker_fleet, "build_fleet_map", return_value=fake):
        data = worker_fleet.health_for("power-1")
    assert data["worker_name"] == "power-1"
    names = [s["name"] for s in data["services"]]
    assert "ollama" not in names
    assert data["tunnel_status"]["expected_ports"] == [8765, 5678]


def test_workers_map_and_health_routes():
    app = FastAPI()
    app.include_router(workers.router)
    fake_map = {
        "ok": True,
        "source": "WORKER_CURRENT.md",
        "checked_at": "2026-01-01T00:00:00Z",
        "nodes": [],
        "primary_worker": "power-1",
        "critical_ok": False,
        "summary": {"power-1": "offline_or_unreachable"},
    }
    fake_health = {
        "worker_name": "power-1",
        "critical_ok": False,
        "worker_status": "offline_or_unreachable",
        "services": [],
        "tunnel_status": {"expected_ports": [8765, 5678]},
        "last_checked": "2026-01-01T00:00:00Z",
        "fleet_summary": {"power-1": "offline_or_unreachable"},
    }
    with patch.object(workers, "build_fleet_map", return_value=fake_map), patch.object(
        workers, "health_for", return_value=fake_health
    ):
        client = TestClient(app)
        r = client.get("/api/workers/map")
        assert r.status_code == 200
        assert r.json()["primary_worker"] == "power-1"
        h = client.get("/api/workers/health")
        assert h.status_code == 200
        assert h.json()["worker_name"] == "power-1"
        alias = client.get("/api/workers/health/worker-rig-01")
        assert alias.status_code == 200
