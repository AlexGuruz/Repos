"""Launch Command Center API as a single process (no --reload / --workers)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

INNER = Path(__file__).resolve().parents[1]  # .../command-center/command-center
BACKEND = INNER / "backend"
AI_LAB = INNER.parents[1]  # .../ai-lab

os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(AI_LAB))
os.environ["PYTHONPATH"] = os.pathsep.join(
    [str(AI_LAB), str(BACKEND)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
)
os.environ.setdefault("OPERATOR_DESK_ENABLED", "1")
# Prefer light mode for stable local Approve/Deny (skip prepared-context warmup contention).
os.environ.setdefault("CC_LIGHT_MODE", "1")

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )
