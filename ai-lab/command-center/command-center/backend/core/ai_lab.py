from __future__ import annotations

import sys
from pathlib import Path


AI_LAB_ROOT = Path(__file__).resolve().parents[4]


def ensure_ai_lab_root_on_path() -> Path:
    root = str(AI_LAB_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return AI_LAB_ROOT
