"""
Worker fleet health. Source of truth: services.worker_fleet (WORKER_CURRENT.md).

GET /api/workers/health defaults to power-1 (not the legacy worker-rig-01 / worker-node name).
GET /api/workers/map returns Acheron + power-1 + worker-node with live port/HTTP probes.
"""
import asyncio

from fastapi import APIRouter

from services.worker_fleet import build_fleet_map, health_for

router = APIRouter()


@router.get("/api/workers/map")
async def workers_map():
    return await asyncio.to_thread(build_fleet_map)


@router.get("/api/workers/health")
async def workers_health():
    """Primary worker (power-1) health + fleet_summary."""
    return await asyncio.to_thread(health_for, "power-1")


@router.get("/api/workers/health/{worker_name}")
async def worker_health_by_name(worker_name: str):
    return await asyncio.to_thread(health_for, worker_name)
