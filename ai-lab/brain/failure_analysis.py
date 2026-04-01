"""
Failure analysis layer (Guru §24.14).

Classifies failure text into category, summary, likely_cause, and suggested_actions
so responses can be sharper. Output shape: { category, summary, likely_cause, suggested_actions[] }.
"""
from __future__ import annotations


def analyze_failure(
    failure_text: str,
    *,
    intent: str = "",
    path: str = "",
) -> dict[str, str | list[str]]:
    """
    Classify failure output. Returns category, summary, likely_cause, suggested_actions.
    Heuristic/keyword-based; can be extended with LLM or rules.
    """
    text = (failure_text or "").lower().strip()
    category = "unknown"
    likely_cause = ""
    suggested_actions: list[str] = []

    if "no such file" in text or "file not found" in text or "path" in text and "exist" in text:
        category = "missing_script_path"
        likely_cause = "Script or path not found."
        suggested_actions = ["search_repos", "inspect_registry", "propose_patch_registry"]
    elif "permission" in text or "denied" in text or "eacces" in text:
        category = "permission_denied"
        likely_cause = "Permission denied."
        suggested_actions = ["check_path_permissions", "run_from_allowed_directory"]
    elif "timeout" in text or "timed out" in text:
        category = "timeout"
        likely_cause = "Operation timed out."
        suggested_actions = ["increase_timeout", "check_network_or_worker"]
    elif "connection" in text or "refused" in text or "unreachable" in text:
        category = "connection_error"
        likely_cause = "Connection refused or host unreachable."
        suggested_actions = ["check_worker_tunnel", "verify_host_and_port"]
    elif "not found" in text or "404" in text:
        category = "not_found"
        likely_cause = "Resource or endpoint not found."
        suggested_actions = ["verify_url_or_path", "check_registry"]
    elif "syntax" in text or "parse" in text or "invalid" in text:
        category = "syntax_or_config"
        likely_cause = "Syntax or configuration error."
        suggested_actions = ["inspect_script_or_config", "run_linter"]
    else:
        suggested_actions = ["inspect_output", "search_repos", "check_registry"]

    summary = text[:300] if text else "No failure output."
    return {
        "category": category,
        "summary": summary,
        "likely_cause": likely_cause or "See summary.",
        "suggested_actions": suggested_actions,
    }
