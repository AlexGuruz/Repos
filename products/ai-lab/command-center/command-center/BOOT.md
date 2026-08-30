# Boot command-center locally (this machine only)

**Path:** Scripts live in the inner app folder, not the ai-lab repo root:

`/mnt/workshop/Repos/products/ai-lab/command-center/command-center/scripts/`

## Linux (Acheron) — daily path

```bash
cd /mnt/workshop/Repos/products/ai-lab/command-center/command-center
./scripts/start.sh
./scripts/harness.sh
```

Compose uses `network_mode: host` for backend **and** frontend so nginx can proxy to `127.0.0.1:8000` and the API can see worker tunnels. Windows `.env` paths are overridden by `docker-compose.yml` (`AI_LAB_ROOT=/ai-lab`, `AI_LAB_GOVERNANCE_ROOT=/governance`).

## Windows (legacy) — FullMode

From the **inner** `command-center` app folder:

```powershell
cd <ai-lab>\command-center\command-center
.\scripts\start.ps1 -FullMode
```

`-FullMode` sets `CC_LIGHT_MODE=0` and starts the real multi-channel stack (telemetry poller, prepared context, etc.).

Plain `.\scripts\start.ps1` (without `-FullMode`) still starts **light mode** (`CC_LIGHT_MODE=1`) for compatibility — **unsafe for multi-channel / investor demo / daily operator use.** Prefer `-FullMode`.

Optional: `-LocalOnly` forces `env.minimal`; can combine: `.\scripts\start.ps1 -FullMode -LocalOnly`.

Two PowerShell windows open (backend + frontend). After ~5 seconds the script opens **http://localhost:5173**. Close both windows to stop.

**Stop or restart without hunting windows:**

```powershell
cd E:\Repos\ai-lab\command-center\command-center
.\scripts\stop.ps1          # kills listeners on ports 8000 + 5173
.\scripts\restart.ps1 -FullMode
.\scripts\restart.ps1 -FullMode -LocalOnly
```

## Option B: If the script fails – do it by hand (4 steps)

**Step 1 – Env**  
Copy the minimal env so the backend can start:
```powershell
cd E:\Repos\ai-lab\command-center\command-center\backend
copy env.minimal .env
```

**Step 2 – Backend (leave this window open)**  
In the same window:
```powershell
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
Wait until you see "Uvicorn running on ...".

**Step 3 – Frontend (new PowerShell window)**  
Open a second PowerShell window:
```powershell
cd E:\Repos\ai-lab\command-center\command-center\frontend
npm install
npm run dev
```
Wait until you see "Local: http://localhost:5173/".

**Step 4 – Open the app**  
In your browser go to: **http://localhost:5173**

---

## If the frontend doesn't start

If you see errors like `vite not found` or PostCSS/caniuse-lite:

1. **Close the frontend (and backend) PowerShell windows** so nothing locks `node_modules`.
2. In the frontend folder, clean and reinstall:
   ```powershell
   cd E:\Repos\ai-lab\command-center\command-center\frontend
   Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
   Remove-Item package-lock.json -ErrorAction SilentlyContinue
   npm install
   ```
3. Run `.\scripts\start.ps1 -FullMode` again from `command-center\command-center`.

**If you see `Cannot find module ... @babel/types/lib/index.js`:** The frontend now uses `@vitejs/plugin-react-swc` (SWC) instead of Babel. Do the clean reinstall above (step 1–3) so dependencies match the updated `package.json`.

---

## If backend dependency install fails (pip / pydantic-core)

**Symptom:** `pip install -r requirements.txt` fails with `pydantic-core` "Rust not found" or "metadata-generation-failed".

**Cause:** The backend uses **Python 3.12 or 3.11**. Python 3.14 has no prebuilt wheels for `pydantic-core` and would require Rust to build from source.

**Fix:**

1. **Use the start script (recommended):** It creates a `.venv` with Python 3.12/3.11 and uses that for the backend. From the `command-center` folder:
   ```powershell
   cd E:\Repos\ai-lab\command-center\command-center
   .\scripts\start.ps1 -FullMode
```
2. **Or install Python 3.12** and use it for deps only:
   ```powershell
   winget install Python.Python.3.12
   ```
   Then run `.\scripts\deps.ps1` (creates `.venv` with 3.12) and start backend/frontend manually, or run `.\scripts\start.ps1 -FullMode` again.
3. **Manual backend with existing .venv:** If you already have a working `.venv` in `command-center\command-center\.venv`:
   ```powershell
   cd E:\Repos\ai-lab\command-center\command-center\backend
   copy env.minimal .env
   ..\.venv\Scripts\pip install -r requirements.txt
   $env:PYTHONPATH = "E:\Repos\ai-lab"
   ..\.venv\Scripts\python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## URLs

| What   | URL |
|--------|-----|
| **UI** | http://localhost:5173 |
| API    | http://localhost:8000 |
| Health | http://localhost:8000/api/health |
| Worker services (tunnel targets) | http://localhost:8000/api/workers/health |
| WS     | ws://localhost:8000/ws/events |

### What `GET /api/workers/health` is for

- **Purpose:** Probes **Worker Assistant** (`/health`), **n8n** (`/`), and **Ollama** (`/api/tags`) using URLs from env (defaults are derived from `WORKER_TUNNEL_URL` in `core/config.py`). Also returns **tunnel port reachability** (`8765`, `5678`, `11434`) via `get_tunnel_status`.
- **Who uses it:** The **Compute** panel and anything else that calls this API (see Guru §26).
- **Normal behavior:** JSON with `services[]`, `tunnel_status`, `all_ok`, `critical_ok` / `worker_assistant_ok`, `last_checked`. Operator green path = **`critical_ok`** (Worker Assistant on `:8765`), not `all_ok` (which also needs n8n + ollama). If `brain` cannot load, you still get JSON with an `error` field (not a dropped connection).

### If PowerShell says “connection closed on receive”

**Typical causes:**

1. **Backend not running** or **wrong port** — nothing stable on `8000`, or a different process bound there.
2. **`uvicorn --reload`** — a file change restarts the worker **while** your request is in flight; the TCP connection can drop mid-response.
3. **`localhost` vs `127.0.0.1`** — try `http://127.0.0.1:8000/api/workers/health` if `localhost` behaves oddly.
4. **Slow/unreachable worker URLs** — each service check has a **3–4s** timeout; the handler runs that work **off the event loop** (thread pool) so the API stays responsive; first hit can still take up to ~10s if all three hang.

**Get the API back up**

```powershell
cd E:\Repos\ai-lab\command-center\command-center
.\scripts\stop.ps1
.\scripts\start.ps1 -FullMode
```

Or manually: backend window must show **Uvicorn running** on `8000`, with `PYTHONPATH` set to your **ai-lab repo root** (see Option B above).

**Quick checks**

```powershell
# Lightweight — proves FastAPI is up
Invoke-RestMethod http://127.0.0.1:8000/api/health

# Worker probes (may take a few seconds)
Invoke-RestMethod http://127.0.0.1:8000/api/workers/health
curl.exe -v http://127.0.0.1:8000/api/workers/health
```

If `/api/health` works but `/api/workers/health` times out, the backend is fine; fix **SSH tunnel** / **WORKER_ASSISTANT_URL** / **WORKER_N8N_URL** / **OLLAMA_HOST** (or unset tunnel URLs so checks fail fast with clear `detail` strings).

Later you can expose only the chat (e.g. via tunnel or reverse proxy) for phone access; the app itself is for controlling this machine and its systems.
