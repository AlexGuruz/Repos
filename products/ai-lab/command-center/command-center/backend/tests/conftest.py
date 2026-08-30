"""
Pytest conftest for command-center backend tests.
Ensures backend root is on sys.path so routers, core, and services import correctly.
"""
from __future__ import annotations

import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))
