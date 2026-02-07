"""
Pytest configuration and fixtures.

Provides common test fixtures and setup for the test suite.
"""
import os
import sys
from pathlib import Path

# Ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default DSNs for local docker-postgres; can be overridden via env
os.environ.setdefault("APP_GLOBAL_DSN", "postgresql://postgres:postgres@localhost:5432/app_global")
os.environ.setdefault("APP_ENTITY_A_DSN", "postgresql://postgres:postgres@localhost:5432/app_entity_a")
os.environ.setdefault("APP_ENTITY_B_DSN", "postgresql://postgres:postgres@localhost:5432/app_entity_b")
