# Testing — ai-lab and command-center

This document describes the test harnesses for the ai-lab core and the command-center backend/frontend.

## Overview

| System | Location | Framework | How to run |
|--------|----------|-----------|------------|
| **ai-lab core** | `ai-lab/tests/` | pytest | From `ai-lab/`: `python -m pytest tests/ -v` |
| **command-center backend** | `ai-lab/command-center/command-center/backend/tests/` | pytest | From `backend/`: `python -m pytest tests/ -v` |

Both use **pytest**. Ensure pytest is installed (`pip install pytest` or use the backend dev requirements below).

---

## ai-lab core tests

- **Config:** `ai-lab/pytest.ini` (testpaths = `tests`, `-v`).
- **Path setup:** `ai-lab/tests/conftest.py` adds the ai-lab root to `sys.path` so `brain` and `agents` import correctly.
- **Coverage:** Router (`classify_intent`), SSH worker config and mocked `run_ssh_command`, cartographer (`run_scan_to_dict`), orchestrator workflow-rules loading and default-answer reply.

**Run (from ai-lab repo root):**

```bash
cd E:\Repos\ai-lab
python -m pytest tests/ -v
```

**Dependencies:** Standard library + `brain`/`agents` (no extra deps beyond what the app uses). Install pytest if needed: `pip install pytest`.

---

## command-center backend tests

- **Config:** `command-center/command-center/backend/pytest.ini` (testpaths = `tests`, `-v`).
- **Path setup:** `backend/tests/conftest.py` adds the backend root to `sys.path` so `routers`, `core`, and `services` import correctly.
- **Coverage:** API endpoint `GET /api/repo/summaries` (empty list and list with JSON summaries), using a temporary dir for `AI_LAB_ROOT` and FastAPI `TestClient`.

**Run (from backend directory):**

```bash
cd ai-lab/command-center/command-center/backend
pip install -r requirements.txt -r requirements-dev.txt   # first time: adds pytest
python -m pytest tests/ -v
```

**Dependencies:** In `requirements.txt` (FastAPI, etc.) plus `requirements-dev.txt` (pytest). `TestClient` is provided by FastAPI.

---

## What is not covered

- **Frontend:** No Jest/Vitest or E2E tests in this repo for the React UI.
- **Full app backend:** Backend tests use a minimal FastAPI app that mounts only the repo router and mocks `AI_LAB_ROOT`; they do not start the full app with lifespan (e.g. no `verify_governance`, no nvidia poller).
- **Live SSH:** SSH worker tests mock `subprocess.run`; no real SSH.
- **Orchestrator end-to-end:** No test that runs the full `run()` path against the real ai-lab tree (only router, cartographer, and workflow-rules loading are tested).

---

## One-time setup

- **ai-lab:** From repo root, `pip install pytest` (or use your project venv).
- **Backend:** From `command-center/command-center/backend/`, `pip install -r requirements.txt -r requirements-dev.txt`.

Running the commands above from the correct directories is sufficient; no extra env vars are required for the current tests.
