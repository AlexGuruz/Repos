from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from routers import hardware


def test_hardware_snapshot_returns_mocked_metrics():
    """Test snapshot endpoint: prefers brain.hardware snapshot when available."""
    app = FastAPI()
    app.include_router(hardware.router)

    mock_snapshot = MagicMock()
    mock_snapshot.to_dict.return_value = {
        "gpu_legacy": {"name": "RTX", "vram_used_gb": 4.2, "utilization_pct": 30, "temp_c": 55},
        "gpu": None,
        "cpu_percent": 17.5,
        "ram_used_gb": 8.1,
        "ram_total_gb": 64.0,
        "timestamp": "2026-01-01T00:00:00Z",
        "cpu": {},
        "node": "local",
    }

    with patch.object(hardware, "_get_snapshot", return_value=mock_snapshot):
        client = TestClient(app)
        response = client.get("/api/hardware/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["gpu"]["name"] == "RTX"
    assert body["cpu_percent"] == 17.5
    assert body["ram_total_gb"] == 64.0
