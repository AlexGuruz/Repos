"""
Pytest conftest: ensure ai-lab root is on path for brain/agents imports.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ai_lab_root = Path(__file__).resolve().parent.parent
if str(_ai_lab_root) not in sys.path:
    sys.path.insert(0, str(_ai_lab_root))
