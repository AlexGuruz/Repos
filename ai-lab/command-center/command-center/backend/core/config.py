import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ai_lab_governance_root: str = ""
    ai_lab_machine: str = "main"
    ai_lab_enforcement: int = 1
    worker_tunnel_url: str = "http://127.0.0.1:8765"
    # httpx timeouts (seconds) for worker tunnel calls.
    worker_bridge_timeout_seconds: float = 30.0
    # Used for index_repo and promote_repo_index (see supervisor_bridge._WORKER_SLOW_OPS).
    worker_bridge_index_repo_timeout_seconds: float = 900.0
    nvidia_smi_poll_interval: int = 5
    log_action_path: str = ""
    registry_path: str = ""
    # Main brain LLM (e.g. LM Studio). Empty = skip model-backed chat.
    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str = "Qwen2.5-Coder-14B-Instruct"
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
        return [x.strip() for x in self.watch_paths.split(os.pathsep) if x.strip()]


settings = Settings()

# Ensure worker URLs are available to child processes spawned by command-center.
# This avoids needing to manually set WORKER_ASSISTANT_URL / WORKER_N8N_URL / OLLAMA_HOST
# when tunnel is up at WORKER_TUNNEL_URL (127.0.0.1 forwarding).
try:
    parsed = urlparse(settings.worker_tunnel_url)
    host = parsed.hostname or "127.0.0.1"

    # Expected tunnel port mapping (set by start_worker_tunnel.ps1):
    #  - 8765 -> worker assistant
    #  - 5678 -> n8n
    #  - 11434 -> Ollama
    os.environ.setdefault("WORKER_ASSISTANT_URL", settings.worker_tunnel_url.rstrip("/"))
    os.environ.setdefault("WORKER_N8N_URL", f"http://{host}:5678")
    os.environ.setdefault("OLLAMA_HOST", f"{host}:11434")
except Exception:
    # Don't block backend startup if URL parsing fails.
    pass


def verify_governance() -> bool:
    """Fail closed if enforcement env is wrong or governance root missing."""
    if settings.ai_lab_enforcement != 1:
        raise RuntimeError("AI_LAB_ENFORCEMENT must be 1 on main rig")
    if settings.ai_lab_machine != "main":
        raise RuntimeError("AI_LAB_MACHINE must be 'main' for command center")
    if settings.ai_lab_governance_root:
        p = Path(settings.ai_lab_governance_root)
        if not p.exists():
            raise RuntimeError(f"Governance root not found: {p}")
    return True
