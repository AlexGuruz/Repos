"""
Tool metadata registry (Guru §24.14).

Single source of truth per tool: name, description, args, side_effects, approval_required, risk_level, output_shape.
Improves proposal generation, approval messaging, and routing consistency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Default in-code registry; can be overridden by ops/registry/tools.yaml
_DEFAULT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "repo_search",
        "description": "Search repositories for files or content matching a query.",
        "args": {"query": "string"},
        "side_effects": "read_only",
        "approval_required": False,
        "risk_level": "low",
        "output_shape": "list of matches with path and snippet",
    },
    {
        "name": "scan_repo",
        "description": "Run repo_cartographer on a repo (worker SSH) and persist summary.",
        "args": {"repo_name": "string"},
        "side_effects": "writes summaries/repos/",
        "approval_required": False,
        "risk_level": "low",
        "output_shape": "scan summary path and status",
    },
    {
        "name": "run_script",
        "description": "Execute a script from the registry by name with optional args.",
        "args": {"script_name": "string", "args": "object"},
        "side_effects": "executes script; may write files or call APIs",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "stdout, stderr, success",
    },
    {
        "name": "set_process_priority",
        "description": "Change process priority or CPU affinity (approval-gated).",
        "args": {"pid": "int", "priority": "optional"},
        "side_effects": "modifies process scheduling",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "success or error",
    },
    {
        "name": "n8n_trigger",
        "description": "Trigger an n8n workflow by name or webhook URL.",
        "args": {"workflow": "string", "payload": "optional"},
        "side_effects": "triggers remote workflow; may run jobs or call APIs",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "response status and body",
    },
    {
        "name": "worker_n8n_trigger",
        "description": "Trigger an n8n workflow on the worker via tunnel.",
        "args": {"workflow": "string", "payload": "optional"},
        "side_effects": "triggers worker n8n workflow",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "response status and body",
    },
    {
        "name": "growflow_sales_today",
        "description": "Fetch today's sales summary from GrowFlow API.",
        "args": {"date": "optional", "location_id": "optional"},
        "side_effects": "read_only",
        "approval_required": False,
        "risk_level": "low",
        "output_shape": "sales summary object",
    },
    {
        "name": "cc_investor_demo_ping",
        "description": "Safe read-only ping used for Command Center approval→execute demos.",
        "args": {},
        "side_effects": "read_only",
        "approval_required": True,
        "risk_level": "low",
        "output_shape": "json ok marker",
    },
    {
        "name": "repo_full_rebuild_gate_a",
        "description": "Force full rebuild in worker staging and promote (Gate A).",
        "args": {"repo_id": "string", "gate": "string"},
        "side_effects": "modifies index state and promotion targets",
        "approval_required": True,
        "risk_level": "high",
        "output_shape": "execution result",
    },
    {
        "name": "repo_policy_migration_gate_c",
        "description": "Force full rebuild for policy/schema migration and promote (Gate C).",
        "args": {"repo_id": "string", "gate": "string"},
        "side_effects": "modifies index state and promotion targets",
        "approval_required": True,
        "risk_level": "high",
        "output_shape": "execution result",
    },
    {
        "name": "rules_sheet_apps_script",
        "description": "Rules sheet Apps Script helper.",
        "args": {},
        "side_effects": "modifies external sheet configuration",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "script execution result",
    },
    {
        "name": "bank_vendor_cleaner_pipeline",
        "description": "Clean bank transaction labels and city/state via scripts/sheet_label_pipeline.py. Default invocation is dry-run preview.",
        "args": {"spreadsheet_id": "optional", "dry_run": "bool", "approved": "bool"},
        "side_effects": "read_only when dry_run=true; writes Google Sheet columns C/D when dry_run=false",
        "approval_required": False,
        "risk_level": "low",
        "output_shape": "run report JSON with rows_processed and preview",
    },
    {
        "name": "bank_vendor_lookup_worker",
        "description": "Propose candidate merchant labels for unknown rows via scripts/vendor_lookup_worker.py. Never writes sheet C/D.",
        "args": {"raw_input": "string", "city_hint": "optional", "state_hint": "optional", "dry_run": "bool"},
        "side_effects": "read_only; may append pending cache and review queue when not dry_run",
        "approval_required": True,
        "risk_level": "medium",
        "output_shape": "candidate label/location JSON with confidence and decision",
    },
]


def _get_ops_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_tool_registry() -> list[dict[str, Any]]:
    """Load tool metadata from ops/registry/tools.yaml if present; else return default list."""
    path = _get_ops_root() / "ops" / "registry" / "tools.yaml"
    if not path.exists():
        return list(_DEFAULT_TOOLS)
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "tools" in data:
            return data["tools"]
        return list(_DEFAULT_TOOLS)
    except Exception:
        return list(_DEFAULT_TOOLS)


def get_tool_metadata(tool_name: str) -> dict[str, Any] | None:
    """Return metadata for a tool by name, or None if not in registry."""
    for t in load_tool_registry():
        if t.get("name") == tool_name:
            return dict(t)
    return None


def list_tool_names() -> list[str]:
    """Return all registered tool names."""
    return [t.get("name", "") for t in load_tool_registry() if t.get("name")]
