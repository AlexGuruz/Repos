from __future__ import annotations

import os
import sys
from pathlib import Path


def _ai_lab_root() -> Path:
    env = os.environ.get("AI_LAB_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    try:
        return here.parents[4]
    except IndexError:
        return Path("/ai-lab")


AI_LAB_ROOT = _ai_lab_root()


def ensure_ai_lab_root_on_path() -> Path:
    root = str(AI_LAB_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return AI_LAB_ROOT
