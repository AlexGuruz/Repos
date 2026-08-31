import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ai_lab_governance_root: str = ""
    ai_lab_machine: str = "main"
    ai_lab_enforcement: int = 1
    worker_tunnel_url: str = "http://127.0.0.1:8765"
    # Fail fast when the tunnel is down (seconds).
    worker_connect_timeout_seconds: float = 5.0
    # httpx read timeout (seconds) for worker tunnel POST/GET (non-index ops).
    worker_bridge_timeout_seconds: float = 45.0
    # Used for index_repo and promote_repo_index (see supervisor_bridge._WORKER_SLOW_OPS).
    worker_bridge_index_repo_timeout_seconds: float = 900.0
    # Comma-separated op names forwarded as read-only worker tunnel calls (POST by default; see supervisor_bridge GET set).
    worker_read_ops_extra: str = ""
    nvidia_smi_poll_interval: int = 5
    log_action_path: str = ""
    registry_path: str = ""
    # Main brain LLM (LM Studio OpenAI-compatible base). Override with LLM_BASE_URL in .env.
    # Must include /v1. Client also uses native POST {host}/api/v1/chat.
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "qwen2.5-coder-14b-instruct"
    llm_max_output_tokens: int = Field(default=1024, ge=256, le=8192)
    # Optional additional repo watcher roots. Use ';' on Windows, ':' on Linux/macOS.
    watch_paths: str = ""

    # Repo indexing hub policy/coordinator settings.
    # Path is resolved relative to the command-center backend working directory.
    index_policy_path: str = "config/index_policy.yaml"
    repo_index_debounce_ms: int = 2500
    repo_index_max_concurrent_builds: int = 2
    repo_index_retry_limit: int = 2
    repo_index_smoke_test_query: str = "where is repo watcher started"
    repo_index_state_path: str = "state/repo_index_state.json"
    # Heuristic for "large delta" classification: number of watcher events in a single dirty generation.
    repo_index_large_delta_events_threshold: int = 80
    # Full-rebuild (Gate A) threshold: if changed_docs_ratio exceeds this, require approval.
    repo_index_changed_docs_ratio_threshold: float = 0.15
    # Full-rebuild (Gate A) threshold: if incremental failures accumulate above this, require approval.
    repo_index_incremental_failure_threshold: int = 3
    # Keep as string in env, parse lazily to avoid JSON decode issues.
    # Allow both localhost and 127.0.0.1 because Vite sometimes binds/redirects
    # to either, and browsers treat them as different origins (CORS).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        # Always include both localhost + 127.0.0.1 for dev servers.
        # This prevents browsers from throwing "Failed to fetch" due to origin mismatch.
        required = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
        from_env = [x.strip() for x in self.cors_origins.split(",") if x.strip()]
        out: list[str] = []
        for o in [*from_env, *required]:
            if o and o not in out:
                out.append(o)
        return out

    @property
    def watch_paths_list(self) -> list[str]:
        if not self.watch_paths.strip():
            return []
        out = []
        for x in self.watch_paths.split(os.pathsep):
            p = x.strip()
            if not p:
                continue
            if os.name != "nt" and len(p) >= 2 and p[1] == ":":
                continue
            out.append(p)
        return out


settings = Settings()

# Ensure worker URLs are available to child processes spawned by command-center.
# This avoids needing to manually set WORKER_ASSISTANT_URL / WORKER_N8N_URL / OLLAMA_HOST
# when tunnel is up at WORKER_TUNNEL_URL (127.0.0.1 forwarding).
try:
    parsed = urlparse(settings.worker_tunnel_url)
    host = parsed.hostname or "127.0.0.1"

    # WORKER_CURRENT.md tunnel map on Acheron:
    #  - power-1: 8765 worker_assistant, 5678 n8n (no Ollama)
    #  - worker-node: 8766 WA, 5679 n8n, 11435 GPU Ollama
    #  - Acheron local Ollama: 127.0.0.1:11434 (not a worker tunnel)
    os.environ.setdefault("WORKER_ASSISTANT_URL", settings.worker_tunnel_url.rstrip("/"))
    os.environ.setdefault("WORKER_N8N_URL", f"http://{host}:5678")
    os.environ.setdefault("OLLAMA_HOST", "127.0.0.1:11434")
    os.environ.setdefault("WORKER_ASSISTANT_URL_SECONDARY", f"http://{host}:8766")
    os.environ.setdefault("WORKER_N8N_URL_SECONDARY", f"http://{host}:5679")
    os.environ.setdefault("OLLAMA_HOST_SECONDARY", f"http://{host}:11435")
except Exception:
    # Don't block backend startup if URL parsing fails.
    pass


def verify_governance() -> bool:
    """Fail closed if enforcement env is wrong or governance root missing."""
    if settings.ai_lab_enforcement != 1:
        raise RuntimeError("AI_LAB_ENFORCEMENT must be 1 on main rig")
    if settings.ai_lab_machine != "main":
        raise RuntimeError("AI_LAB_MACHINE must be 'main' for command center")
    raw = os.environ.get("AI_LAB_GOVERNANCE_ROOT") or settings.ai_lab_governance_root
    if raw:
        windows_drive = os.name != "nt" and len(raw) >= 2 and raw[1] == ":"
        p = Path("/governance") if windows_drive else Path(raw)
        if not p.exists():
            fallback = Path("/governance")
            if fallback.exists():
                p = fallback
            else:
                linux_default = Path("/mnt/workshop/Repos/products/ai-lab-governance")
                if linux_default.exists():
                    p = linux_default
                else:
                    raise RuntimeError(f"Governance root not found: {raw}")
        os.environ["AI_LAB_GOVERNANCE_ROOT"] = str(p)
        settings.ai_lab_governance_root = str(p)
    return True
