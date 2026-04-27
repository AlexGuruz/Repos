"""
Approval gate (Guru §21). Determines if an action can run immediately or requires approval.
Consults tool_registry when available (Guru §24.14).
"""
from __future__ import annotations

# Tier 1: auto-allowed (read-only)
AUTO_ALLOWED = frozenset({
    "read", "load", "scan", "search", "repo_scan", "repo_search", "web_search",
    "show_scan_results", "scan_results", "inspect", "dry_run", "validate",
    "ops_overview", "worker_health",
})

# Tier 2/3: approval required (writes / state changes / resource control — Guru §25)
APPROVAL_REQUIRED = frozenset({
    "patch", "edit", "write", "update_registry", "patch_registry", "create",
    "modify", "delete", "commit", "push", "send", "notify", "calendar",
    "set_process_priority", "process_priority", "set_cpu_affinity", "cpu_affinity",
    "run_script", "n8n_trigger", "worker_n8n_trigger",
    "restart_service", "modify_registry", "write_sheet", "run_approved", "submit_approval",
})


def _tool_approval_required(action: str, tool: str | None) -> bool | None:
    """Return approval_required from tool_registry if present; else None."""
    try:
        from brain.tool_registry import get_tool_metadata
        key = (tool or action or "").strip()
        if not key:
            return None
        meta = get_tool_metadata(key)
        if meta is not None and "approval_required" in meta:
            return bool(meta["approval_required"])
    except Exception:
        pass
    return None


def requires_approval(action: str, tool: str | None = None) -> bool:
    """
    Return True if the action must go through approval before execution.
    Consults tool_registry first when available; else uses hardcoded sets.
    """
    a = (action or "").lower()
    t = (tool or "").lower()
    reg = _tool_approval_required(a, t or a)
    if reg is not None:
        return reg
    if a in AUTO_ALLOWED or t in AUTO_ALLOWED:
        return False
    if a in APPROVAL_REQUIRED or t in APPROVAL_REQUIRED:
        return True
    for prefix in ("patch_", "update_", "edit_", "write_", "create_", "delete_"):
        if a.startswith(prefix) or t.startswith(prefix):
            return True
    return False
