from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RepoIndexStateStore:
    def __init__(self, state_path: str | Path):
        self.state_path = Path(state_path)

    def load(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self, repo_states: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(repo_states, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.state_path)

