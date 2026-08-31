"""Operator Desk — public package exports."""
from __future__ import annotations

from .approvals import list_pending_approvals, submit_tool_proposal
from .fast_path import try_fast_reply
from .intent_map import resolve_job_id_for_message, resolve_intent_key
from .job_primer import load_job_primer, load_job_manifest
from .settings import get_settings, clear_settings_cache
from .tools.email_ops import fetch_unread_digest, propose_draft_reply
from .tools.growflow_ops import (
    get_growflow_bi_summary,
    get_growflow_capital,
    get_growflow_catalog,
    get_growflow_consignment,
    get_growflow_projection,
    get_growflow_retail,
    get_growflow_status,
)
from .tools.machine_ops import list_pending, propose_allowlisted_action
from .tools.repo_ops import get_repo_map_summary

__all__ = [
    "get_settings",
    "clear_settings_cache",
    "load_job_primer",
    "load_job_manifest",
    "resolve_job_id_for_message",
    "resolve_intent_key",
    "try_fast_reply",
    "get_growflow_status",
    "get_growflow_retail",
    "get_growflow_capital",
    "get_growflow_consignment",
    "get_growflow_projection",
    "get_growflow_bi_summary",
    "get_growflow_catalog",
    "fetch_unread_digest",
    "propose_draft_reply",
    "list_pending_approvals",
    "list_pending",
    "submit_tool_proposal",
    "propose_allowlisted_action",
    "get_repo_map_summary",
]

__version__ = "0.1.0"
