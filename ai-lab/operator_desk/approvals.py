"""Approval-gated proposals — brain queue only (B1). Allowlist scripts.json (B2)."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import paths as pathmod
from .errors import (
    ACTION_NOT_ALLOWLISTED,
    APPROVAL_SERVICE_UNAVAILABLE,
    OperatorError,
)
from .models import ApprovalSubmissionResult, MachinePendingItem, MachinePendingResult

_SHELL_META = re.compile(r"[;&|`$<>]|(\.\./)")


@lru_cache(maxsize=1)
def _allowed_tool_names() -> frozenset[str]:
    path = pathmod.scripts_registry_path()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return frozenset()
    names: set[str] = set()
    for row in data:
        if isinstance(row, dict) and row.get("tool_name"):
            names.add(str(row["tool_name"]))
    return frozenset(names)


def clear_scripts_cache() -> None:
    _allowed_tool_names.cache_clear()


def _reject_raw_shell_args(args: dict[str, Any]) -> None:
    forbidden_keys = {"command", "cmd", "shell", "powershell", "bash", "executable", "script_path"}
    for key, value in args.items():
        lk = str(key).lower()
        if lk in forbidden_keys:
            raise OperatorError(ACTION_NOT_ALLOWLISTED, f"Disallowed arg key: {key}")
        if isinstance(value, str) and _SHELL_META.search(value):
            raise OperatorError(ACTION_NOT_ALLOWLISTED, f"Shell metacharacters in arg {key}")


def list_pending_approvals() -> MachinePendingResult:
    path = pathmod.approval_pending_path()
    if not path.is_file():
        return MachinePendingResult(
            ok=True,
            source="approval_queue",
            freshness="fresh",
            items=[],
            warnings=["pending.json missing — treating as empty"],
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return MachinePendingResult(
            ok=False,
            source="approval_queue",
            freshness="unavailable",
            error_code=APPROVAL_SERVICE_UNAVAILABLE,
            degraded=True,
            warnings=[str(exc)],
        )
    if not isinstance(raw, dict):
        return MachinePendingResult(
            ok=False,
            source="approval_queue",
            freshness="degraded",
            error_code=APPROVAL_SERVICE_UNAVAILABLE,
            degraded=True,
            warnings=["pending.json is not an object"],
        )
    items: list[MachinePendingItem] = []
    for approval_id, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        items.append(
            MachinePendingItem(
                approval_id=str(approval_id),
                action_type=str(spec.get("action_type", "")),
                reason=str(spec.get("reason", "")),
                risk_level=str(spec.get("risk_level", "medium")),
                created_at=spec.get("created_at"),
                tool_name=spec.get("tool_name"),
            )
        )
    return MachinePendingResult(
        ok=True,
        source="approval_queue",
        freshness="fresh",
        items=items,
    )


def submit_tool_proposal(
    tool_name: str,
    args: dict[str, Any] | None,
    *,
    reason: str,
    risk_level: str = "medium",
    action_type: str = "operator_desk_tool",
    file_path: str = "operator_desk",
) -> ApprovalSubmissionResult:
    """Enqueue brain approval with mandatory tool_name/args.

    If a durable permanent allowlist rule matches, skip the pending card and
    return ``approval_required=False`` (auto path). Command Center should then
    execute via the same approved-run path as Always Approve.
    """
    name = (tool_name or "").strip()
    if name not in _allowed_tool_names():
        raise OperatorError(ACTION_NOT_ALLOWLISTED, f"tool_name not in scripts.json: {name}")
    payload_args = dict(args or {})
    _reject_raw_shell_args(payload_args)

    try:
        from brain.approval_queue.queue import submit
        from brain.permanent_allowlist import brain_spec_match_payload, find_matching_rule
    except ImportError as exc:
        raise OperatorError(
            APPROVAL_SERVICE_UNAVAILABLE,
            "brain.approval_queue unavailable",
        ) from exc

    probe = brain_spec_match_payload(
        {
            "file_path": file_path,
            "action_type": action_type,
            "tool_name": name,
            "reason": reason,
        }
    )
    rule = find_matching_rule(action_type, probe)
    if rule:
        rid = str(rule.get("id") or "")
        try:
            from brain.approval_queue.queue import resolve as queue_resolve
            from brain.execution import run as execution_run
        except ImportError as exc:
            raise OperatorError(
                APPROVAL_SERVICE_UNAVAILABLE,
                "brain resolve/execution unavailable",
            ) from exc
        try:
            approval_id = submit(
                {
                    "file_path": file_path,
                    "action_type": action_type,
                    "reason": reason,
                    "risk_level": risk_level,
                    "agent": "operator_desk",
                    "tool_name": name,
                    "args": payload_args,
                }
            )
            if not queue_resolve(approval_id, True):
                raise OperatorError(
                    APPROVAL_SERVICE_UNAVAILABLE,
                    f"permanent match could not resolve {approval_id}",
                )
            result = execution_run(
                name,
                payload_args,
                300,
                approval_context={
                    "approved": True,
                    "approval_id": approval_id,
                    "source": "operator_desk.permanent_auto",
                    "permanent_rule_id": rid,
                },
            )
        except OperatorError:
            raise
        except Exception as exc:
            raise OperatorError(APPROVAL_SERVICE_UNAVAILABLE, str(exc)) from exc

        warnings = [f"Matched permanent rule {rid}; auto-approved and executed"]
        if not result.success:
            warnings.append(
                f"execution_failed: {(result.stderr or result.stdout or 'unknown')[:300]}"
            )
        return ApprovalSubmissionResult(
            ok=bool(result.success),
            source="approval_queue",
            freshness="fresh",
            approval_required=False,
            approval_id=approval_id,
            tool_name=name,
            status="auto_approved" if result.success else "auto_approved_exec_failed",
            auto_permanent=True,
            permanent_rule_id=rid or None,
            act_id=f"ACT-{approval_id}",
            execute_queued=False,
            degraded=not result.success,
            warnings=warnings,
        )

    try:
        approval_id = submit(
            {
                "file_path": file_path,
                "action_type": action_type,
                "reason": reason,
                "risk_level": risk_level,
                "agent": "operator_desk",
                "tool_name": name,
                "args": payload_args,
            }
        )
    except Exception as exc:
        raise OperatorError(APPROVAL_SERVICE_UNAVAILABLE, str(exc)) from exc

    return ApprovalSubmissionResult(
        ok=True,
        source="approval_queue",
        freshness="fresh",
        approval_required=True,
        approval_id=approval_id,
        tool_name=name,
        status="pending",
    )
