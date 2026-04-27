"""
Orchestrator: parse user message, classify intent, consult registry/memory, apply policy, run or enqueue approval.
V1: session state, structured tool results, evidence loading, scan_results intent, anti-hallucination.
Guru §24.13: normalize_chat_text, allowlist-only early conversational gate. §24.14: per-turn trace, transparency line.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

# Add ai-lab root
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from brain.router.router import classify_intent
from brain.execution import run as execution_run, RunResult
from brain.approval_queue.queue import submit, list_pending, resolve, ApprovalSpec
from brain.permanent_allowlist import find_matching_rule, brain_spec_match_payload
from brain.ssh_worker import get_worker_ssh_config, run_ssh_command
from brain.llm_client import chat_completion
from brain import session_state
from brain import repo_search as repo_search_mod
from brain.schemas.proposals import ProposalRecord
from brain import source_selection
from brain import web_tool
from brain.telemetry import log_event
from brain.approval_enforcement import evaluate_action
from brain.orchestrator.response_trace import (
    StageTimer,
    append_response_trace,
    first_token_tracker,
    new_request_id,
)


def _load_registry() -> list:
    p = _root / "registry" / "scripts.json"
    if not p.exists():
        return []
    with open(p) as f:
        return json.load(f)


def _load_workflow_rules() -> list[dict]:
    """Load Guru-written workflow rules from memory (runtime consumption). Used when answering."""
    p = _root / "memory" / "workflow_rules.json"
    if not p.exists():
        return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


# Guru §24.13: default allowlist for early conversational gate (policy can override)
_DEFAULT_CONVERSATIONAL_OPENERS = [
    "hi", "hello", "hey", "yo", "sup", "what's up",
    "good morning", "good afternoon", "good evening",
    "help", "what can you do",
]

# Cache allowlist reads (mtime-invalidated); avoids YAML disk I/O every chat turn.
_OPENERS_CACHE: tuple[float | None, list[str]] = (None, [])


def _sanitize_chat_input(message: str) -> str:
    """Strip BOM, normalize smart quotes, collapse whitespace (early gate + routing)."""
    if not message:
        return ""
    s = message.strip()
    if s.startswith("\ufeff"):
        s = s.lstrip("\ufeff").strip()
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_chat_text(message: str) -> str:
    """Normalize for allowlist matching: strip, lower, remove trailing [!?.,]+ (Guru §24.13 Fix 3)."""
    if not message:
        return ""
    s = message.strip().lower()
    s = re.sub(r"[!?.,]+$", "", s).strip()
    return s


def _load_conversational_openers() -> list[str]:
    """Load conversational openers from policy/allowlists.yaml (key: conversational_openers). Fallback: default list."""
    global _OPENERS_CACHE
    path = _root / "policy" / "allowlists.yaml"
    mtime: float | None = None
    try:
        mtime = path.stat().st_mtime if path.exists() else None
    except OSError:
        mtime = None
    sentinel = mtime if mtime is not None else -1.0
    if _OPENERS_CACHE[0] == sentinel and _OPENERS_CACHE[1]:
        return _OPENERS_CACHE[1]

    if not path.exists():
        result = list(_DEFAULT_CONVERSATIONAL_OPENERS)
        _OPENERS_CACHE = (sentinel, result)
        return result
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and data.get("conversational_openers"):
            raw = data["conversational_openers"]
            result = [normalize_chat_text(str(x)) for x in (raw if isinstance(raw, list) else [raw]) if x]
        else:
            result = list(_DEFAULT_CONVERSATIONAL_OPENERS)
    except Exception:
        result = list(_DEFAULT_CONVERSATIONAL_OPENERS)
    _OPENERS_CACHE = (sentinel, result)
    return result


def _is_short_social_greeting(normalized: str) -> bool:
    """
    Brief greetings / thanks without task keywords — catches 'hello there', 'hey!', etc.
    that would otherwise miss the exact allowlist and hit web+LLM.
    """
    if not normalized or len(normalized) > 64:
        return False
    task_kw = (
        "scan", "repo", "repos", "search", "script", "fail", "error",
        "weather", "sales", "index", "worker", "gpu", "cpu", "ollama", "n8n", "growflow",
        "registry", "patch", "tunnel", "hardware", "approve", "deny", "do it",
    )
    if any(k in normalized for k in task_kw):
        return False
    words = re.split(r"[\s,]+", normalized)
    words = [w for w in words if w]
    # Standalone command-ish tokens (avoid treating "hey run this" as a greeting)
    if frozenset(words) & frozenset({
        "run", "scan", "search", "exec", "execute", "show", "list", "get", "set", "fix", "build",
        "deploy", "start", "stop", "kill", "open", "read", "write", "delete", "summarize", "explain",
    }):
        return False
    if not words:
        return False
    w0 = words[0]
    if w0 in ("hi", "hello", "hey", "yo", "sup", "greetings", "thanks", "thank", "thx", "ok", "okay", "cheers", "morning", "afternoon", "evening"):
        return True
    if normalized.startswith(("good morning", "good afternoon", "good evening")):
        return True
    if normalized in ("what's up", "whats up", "wassup", "howdy"):
        return True
    if normalized.startswith(("hello ", "hey ", "hi ", "thanks ", "thank you")):
        return True
    return False


def _run_tool(tool_name: str, args: dict | None) -> RunResult:
    return execution_run(tool_name, args or {})


def _load_artifact_content(path: str) -> str | None:
    """Load file content for evidence. Returns None if unreadable."""
    try:
        p = Path(path)
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def build_grounded_response(
    *,
    session_id: str,
    message: str,
    intent: str,
    entities: list[str] | None = None,
) -> dict:
    """
    Full pipeline (Guru §21): freshness -> session resolution -> route -> load -> fuse -> proposals.
    Returns evidence_block (for LLM), proposals_suffix (to append to reply), answer_style, routing_reason.
    """
    from brain.orchestrator.freshness import detect_freshness
    from brain.orchestrator.session_resolution import resolve_session_references
    from brain.orchestrator.source_router import route_sources
    from brain.orchestrator.evidence_loader import load_evidence
    from brain.orchestrator.evidence_fusion import fuse_evidence
    from brain.orchestrator.strategies import choose_answer_style
    from brain.orchestrator.proposal_engine import build_proposals

    session = session_state.get(session_id)
    entities = entities or []
    st = StageTimer()
    freshness = detect_freshness(message)
    st.segment("detect_freshness")
    resolved = resolve_session_references(message, session)
    st.segment("session_resolution")
    decision = route_sources(
        message=message,
        intent=intent,
        entities=entities,
        session=session,
        freshness=freshness,
        resolved=resolved,
    )
    st.segment("route_sources")
    evidence = load_evidence(decision, session_id)
    st.segment("load_evidence")
    fused = fuse_evidence(message=message, intent=intent, decision=decision, evidence=evidence)
    proposals = build_proposals(fused)
    answer_style = choose_answer_style(fused)
    st.segment("fuse_evidence_and_proposals")

    _cat = ""
    try:
        from brain.catalog_loader import format_catalog_grounding_for_message

        _cat = format_catalog_grounding_for_message(message) or ""
    except Exception:
        _cat = ""

    # Structured FusedContext → prompt (PDR Phase 2.75)
    def _format_evidence(items, max_items: int, max_chars_per: int) -> str:
        out: list[str] = []
        for item in items[:max_items]:
            if item.content:
                out.append(f"[{item.source_type}]{f' ({item.title})' if item.title else ''}:\n---\n{item.content[:max_chars_per]}\n---")
        return "\n\n".join(out) if out else "(none)"

    key_evidence_text = _format_evidence(fused.key_evidence, 3, 6000)
    secondary_evidence_text = _format_evidence(fused.secondary_evidence, 2, 2000)
    time_context_text = str(fused.time_context) if fused.time_context else "(none)"
    constraints_text = "; ".join(fused.constraints[:5]) if fused.constraints else "(none)"
    template_path = _root / "brain" / "prompts" / "grounded_prompt.txt"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
        evidence_block = template.format(
            resolved_question=fused.resolved_question or message,
            active_topic=fused.active_topic or "(none)",
            key_evidence=key_evidence_text or "(none)",
            secondary_evidence=secondary_evidence_text or "(none)",
            time_context=time_context_text,
            constraints=constraints_text,
            answer_style=answer_style,
        )
    else:
        evidence_block = (
            f"Resolved: {fused.resolved_question or message}\n"
            f"Topic: {fused.active_topic or '(none)'}\n"
            f"Key evidence:\n{key_evidence_text}\n"
            f"Secondary:\n{secondary_evidence_text}\n"
            f"Constraints: {constraints_text}\n"
            f"Answer style: {answer_style}"
        )
    st.segment("format_prompt_block")

    if _cat:
        evidence_block = _cat + "\n\n" + evidence_block

    proposals_suffix = ""
    if proposals:
        lines: list[str] = []
        for i, p in enumerate(proposals[:4]):
            approval = "yes" if getattr(p, "approval_required", True) else "no"
            proceed = "say **approve**" if approval == "yes" else "say **do it**"
            lines.append(f"{i+1}. **{p.title}** — approval required: **{approval}**; to proceed: {proceed}")
        proposals_suffix = "\n\n**Suggested next steps:**\n" + "\n".join(lines)

    session_state.set_last_routing_decision(session_id, {
        "intent": intent,
        "answer_style": answer_style,
        "reason": decision.reason,
    })

    source_types: list[str] = []
    for it in evidence.local_evidence + evidence.web_evidence:
        source_types.append(it.source_type)
    if evidence.time_context:
        source_types.append("time_context")

    return {
        "evidence_block": evidence_block,
        "proposals_suffix": proposals_suffix,
        "answer_style": answer_style,
        "routing_reason": decision.reason,
        "proposals": proposals,
        "stage_timings_ms": dict(st.segments_ms),
        "evidence_count": len(evidence.local_evidence) + len(evidence.web_evidence) + (1 if evidence.time_context else 0),
        "sources_used": source_types,
    }


# Defaults from Ai/LOCAL_AI_START_HERE.md (LM Studio)
_DEFAULT_LLM_BASE_URL = "http://100.71.161.10:1234/v1"
_DEFAULT_LLM_MODEL = "Qwen2.5-Coder-14B-Instruct"


def _write_turn_trace_if_enabled(
    *,
    write: bool,
    req_id: str,
    session_id: str,
    user_message: str,
    route: str,
    model: str,
    worker_used: bool,
    run_timer: StageTimer,
    extra_stage_timings_ms: dict[str, float],
    first_token_ms: float | None,
    first_token_wall_ms: float | None,
    receive_wall_ms: float | None,
    client_submit_epoch_ms: float | None,
    evidence_count: int,
    sources_used: list[str],
    fallback_reason: str | None,
    final_answer_type: str,
    reply_preview: str,
    prepared_context_used: bool = False,
    snapshot_types_used: list[str] | None = None,
    snapshot_generated_at: dict[str, str] | None = None,
    snapshot_stale: bool | None = None,
    context_load_ms: float | None = None,
    avoided_retrieval: bool | None = None,
    avoided_worker_call: bool | None = None,
    final_answer_source: str | None = None,
    prepared_quality_score: float | None = None,
    prepared_quality_reasons: dict | None = None,
    prepared_quality_low: bool | None = None,
) -> None:
    if not write:
        return
    total = run_timer.total_ms()
    ft_ms = first_token_ms if first_token_ms is not None else total
    ft_wall = first_token_wall_ms
    if ft_wall is None and receive_wall_ms is not None:
        ft_wall = receive_wall_ms + ft_ms
    recv_to_first = None
    if receive_wall_ms is not None and ft_wall is not None:
        recv_to_first = round(ft_wall - receive_wall_ms, 2)
    client_to_first = None
    if client_submit_epoch_ms is not None and ft_wall is not None:
        client_to_first = round(ft_wall - client_submit_epoch_ms, 2)
    merged = dict(run_timer.segments_ms)
    merged.update(extra_stage_timings_ms or {})
    append_response_trace(
        {
            "request_id": req_id,
            "session_id": session_id,
            "user_message": (user_message or "")[:1200],
            "route_chosen": route,
            "model": model or "",
            "worker_used": worker_used,
            "stage_timings_ms": merged,
            "first_token_ms": ft_ms,
            "receive_to_first_token_ms": recv_to_first,
            "client_epoch_to_first_token_ms": client_to_first,
            "total_ms": total,
            "evidence_count": evidence_count,
            "sources_used": sources_used,
            "fallback_reason": fallback_reason,
            "final_answer_type": final_answer_type,
            "reply_preview": (reply_preview or "")[:400],
            "prepared_context_used": prepared_context_used,
            "snapshot_types_used": snapshot_types_used or [],
            "snapshot_generated_at": snapshot_generated_at or {},
            "snapshot_stale": snapshot_stale,
            "context_load_ms": context_load_ms,
            "avoided_retrieval": avoided_retrieval,
            "avoided_worker_call": avoided_worker_call,
            "final_answer_source": final_answer_source or "unknown",
            "prepared_quality_score": prepared_quality_score,
            "prepared_quality_reasons": prepared_quality_reasons or {},
            "prepared_quality_low": prepared_quality_low,
        }
    )


def run(
    message: str,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    session_id: str = "default",
    stream_delta: Callable[[str], None] | None = None,
    *,
    request_id: str | None = None,
    client_submit_epoch_ms: float | None = None,
    receive_wall_ms: float | None = None,
    write_response_trace: bool = True,
) -> dict:
    """
    Process user message. Returns {"reply": str, "approval_request": dict|None}.
    V1: session_id used for working memory (last scan, last failure, etc.).

    request_id: optional stable id for structured traces (command-center supplies UUID).
    client_submit_epoch_ms: optional browser Date.now() at send (epoch ms) for client↔server skew diagnostics.
    receive_wall_ms: optional server wall ms (time.time()*1000) when HTTP handler received the message.
    write_response_trace: append one JSON line to state/ai_response_traces.jsonl when True.
    """
    req_id = (request_id or "").strip() or new_request_id()
    run_timer = StageTimer()
    mark_first_token, first_token_elapsed = first_token_tracker()
    first_token_wall_ms: list[float | None] = [None]

    def _mark_first_token() -> None:
        mark_first_token()
        if first_token_wall_ms[0] is None:
            first_token_wall_ms[0] = time.time() * 1000.0

    msg = _sanitize_chat_input(message or "")
    # Guru §24.13: Hard early conversational gate — allowlist + short social phrases; before intent/evidence pipeline
    normalized = normalize_chat_text(msg)
    openers = _load_conversational_openers()
    if normalized in openers or _is_short_social_greeting(normalized):
        help_phrases = {"help", "what can you do"}
        if normalized in help_phrases:
            log_event("conversational_fallback", session_id=session_id, kind="capability_overview")
            rep = (
                "I can help with:\n"
                "- repo scans + scan summaries\n"
                "- diagnosing failures from real tool output\n"
                "- searching repos for files/scripts\n"
                "- grounded answers with local + web + time evidence\n"
                "- proposals + approval-gated execution\n"
                "- hardware status (CPU/GPU/RAM) and approval-gated resource controls\n\n"
                "Tell me what to do (e.g. “scan my repos”, “why did that fail”, “what’s my hardware doing”)."
            )
            _write_turn_trace_if_enabled(
                write=write_response_trace,
                req_id=req_id,
                session_id=session_id,
                user_message=msg,
                route="greeting_help",
                model="",
                worker_used=False,
                run_timer=run_timer,
                extra_stage_timings_ms={},
                first_token_ms=first_token_elapsed(),
                first_token_wall_ms=first_token_wall_ms[0],
                receive_wall_ms=receive_wall_ms,
                client_submit_epoch_ms=client_submit_epoch_ms,
                evidence_count=0,
                sources_used=[],
                fallback_reason=None,
                final_answer_type="greeting_help",
                reply_preview=rep,
                final_answer_source="tool",
            )
            return {"reply": rep, "approval_request": None}
        topic = session_state.get_active_topic(session_id) or "(none)"
        log_event("conversational_fallback", session_id=session_id, kind="greeting", active_topic=topic)
        rep2 = f"Ready. Active topic: **{topic}**. What do you want to work on?"
        _write_turn_trace_if_enabled(
            write=write_response_trace,
            req_id=req_id,
            session_id=session_id,
            user_message=msg,
            route="greeting_shortcircuit",
            model="",
            worker_used=False,
            run_timer=run_timer,
            extra_stage_timings_ms={},
            first_token_ms=first_token_elapsed(),
            first_token_wall_ms=first_token_wall_ms[0],
            receive_wall_ms=receive_wall_ms,
            client_submit_epoch_ms=client_submit_epoch_ms,
            evidence_count=0,
            sources_used=[],
            fallback_reason=None,
            final_answer_type="greeting_shortcircuit",
            reply_preview=rep2,
            final_answer_source="tool",
        )
        return {"reply": rep2, "approval_request": None}
    if msg.lower().startswith("approve ") or msg.lower().startswith("deny "):
        parts = msg.split(None, 1)
        action, id_ = parts[0].lower(), (parts[1].strip() if len(parts) > 1 else None)
        if id_:
            ok = resolve(id_, action == "approve")
            if ok:
                try:
                    from agents.feedback_interpreter.interpreter import apply_feedback
                    apply_feedback(message, {"approval_id": id_})
                except Exception:
                    pass
                return {"reply": f"Recorded {action} for {id_}.", "approval_request": None}
        pending = list_pending()
        return {"reply": f"Unknown id or usage: approve <id> / deny <id>. Pending: {[p[0] for p in pending]}", "approval_request": None}
    intent, params = classify_intent(message)
    run_timer.segment("intent_classification")
    log_event("intent", session_id=session_id, intent=intent, params=params)

    # Prepared context fast path: answer from cached intelligence before retrieval/model.
    if intent in ("answer", "ops_overview", "company_bi"):
        try:
            from brain.prepared_context.loader import try_prepared_context_answer

            pctx = try_prepared_context_answer(msg, intent)
        except Exception:
            pctx = None
        if pctx and pctx.get("reply"):
            reply = pctx["reply"]
            _write_turn_trace_if_enabled(
                write=write_response_trace,
                req_id=req_id,
                session_id=session_id,
                user_message=msg,
                route=intent,
                model="",
                worker_used=False,
                run_timer=run_timer,
                extra_stage_timings_ms={},
                first_token_ms=first_token_elapsed(),
                first_token_wall_ms=first_token_wall_ms[0],
                receive_wall_ms=receive_wall_ms,
                client_submit_epoch_ms=client_submit_epoch_ms,
                evidence_count=len(pctx.get("snapshot_types_used") or []),
                sources_used=list(pctx.get("snapshot_types_used") or []),
                fallback_reason=None,
                final_answer_type="prepared_context",
                reply_preview=reply,
                prepared_context_used=True,
                snapshot_types_used=list(pctx.get("snapshot_types_used") or []),
                snapshot_generated_at=dict(pctx.get("snapshot_generated_at") or {}),
                snapshot_stale=bool(pctx.get("snapshot_stale")),
                context_load_ms=float(pctx.get("context_load_ms") or 0.0),
                avoided_retrieval=bool(pctx.get("avoided_retrieval")),
                avoided_worker_call=bool(pctx.get("avoided_worker_call")),
                final_answer_source=str(pctx.get("final_answer_source") or "prepared_context"),
                prepared_quality_score=float(pctx.get("prepared_quality_score") or 0.0),
                prepared_quality_reasons=dict(pctx.get("prepared_quality_reasons") or {}),
                prepared_quality_low=bool(pctx.get("prepared_quality_low")),
            )
            return {"reply": reply, "approval_request": None}

    if intent == "enqueue_approval":
        pending_prop = session_state.get_pending_proposal(session_id)
        path_str = ""
        action_type = "manual_enqueue"
        reason = msg[:500]
        if pending_prop:
            pargs = pending_prop.get("args") or {}
            path_str = (pargs.get("target") or pargs.get("file_path") or "").strip()
            action_type = str(pending_prop.get("action") or action_type)
            reason = str(pending_prop.get("description") or pending_prop.get("title") or reason)[:500]
        if not path_str:
            default_reg = _root / "registry" / "scripts.json"
            path_str = str(default_reg if default_reg.is_file() else (_root / "README.md"))
        perm_probe = brain_spec_match_payload(
            {"file_path": path_str, "action_type": action_type, "reason": reason}
        )
        if find_matching_rule(action_type, perm_probe):
            log_event(
                "approval_skipped_permanent",
                session_id=session_id,
                action_type=action_type,
                path=path_str,
            )
            return {
                "reply": (
                    f"A **permanent approval** rule matched for `{action_type}` on `{path_str}`. "
                    "No approval card was created."
                ),
                "approval_request": None,
            }
        spec = ApprovalSpec(
            file_path=path_str,
            action_type=action_type,
            reason=reason or "Approval enqueue from chat",
        )
        aid = submit(spec)
        spec_row: dict | None = None
        for pid, row in list_pending():
            if pid == aid:
                spec_row = row
                break
        catalog_ctx = (spec_row or {}).get("catalog_context")
        apr = {
            "id": aid,
            "agent": "orchestrator",
            "action_type": (spec_row.get("action_type") if spec_row else None) or action_type,
            "reason": (spec_row.get("reason") if spec_row else None) or reason,
            "created_at": (spec_row or {}).get("created_at") or datetime.now(timezone.utc).isoformat(),
            "catalog_context": catalog_ctx,
            "file_path": path_str,
            "payload": brain_spec_match_payload(spec_row)
            if spec_row
            else brain_spec_match_payload(
                {"file_path": path_str, "action_type": action_type, "reason": reason}
            ),
        }
        log_event("approval_enqueued", session_id=session_id, approval_id=aid, file_path=path_str)
        return {
            "reply": (
                f"Queued **{aid}** for `{path_str}`. "
                f"Say `approve {aid}` or `deny {aid}`, or use the sidebar APR controls."
            ),
            "approval_request": apr,
        }

    # PDR Phase 2.75: increment turn and expire stale proposals
    session_state.increment_turn(session_id)
    if session_state.is_proposal_expired(session_id):
        session_state.clear_pending_proposal(session_id)
        log_event("proposal_expired", session_id=session_id)

    if intent == "run" and params.get("tool_hint"):
        tool_name = params["tool_hint"]
        args = params.get("args") or {}
        result = _run_tool(tool_name, args)
        outcome = "success" if result.success else "failed"
        log_event(
            "turn_trace",
            session_id=session_id,
            message=message[:200],
            intent=intent,
            sources_used="",
            proposals_created=0,
            execution_attempted=True,
            outcome=outcome,
            tool=tool_name,
        )
        if result.success:
            reply = f"Ran **{tool_name}**. Output:\n```\n{result.stdout or '(no output)'}\n```"
        else:
            session_state.update_after_tool(
                session_id,
                tool_name,
                "failed",
                failure_reason=result.stderr or result.stdout or "unknown",
                failure_path=params.get("path"),
            )
            if "growflow" in (tool_name or "").lower() or "sales" in (tool_name or "").lower():
                session_state.update_active_topic(session_id, "growflow_sales_failure")
            else:
                session_state.update_active_topic(session_id, "tool_failure")
            reply = f"Run failed: {result.stderr or result.stdout or 'unknown'}"
        return {"reply": reply, "approval_request": None}

    if intent == "approval_explain":
        ref = (params.get("ref") or "").strip()
        pending_map = dict(list_pending())
        aid = ref if ref in pending_map else ref.replace("_", "-")
        spec = pending_map.get(aid)
        if not spec and ref.lower().startswith("apr-") and ref[4:].isdigit():
            aid = f"approval-{ref.split('-', 1)[-1]}"
            spec = pending_map.get(aid)
        if not spec:
            keys = list(pending_map.keys())
            if keys:
                reply = f"No pending approval **`{ref}`** in the queue. Pending now: **{keys}**."
            else:
                reply = f"No pending approval **`{ref}`** (queue is empty)."
            return {"reply": reply, "approval_request": None}
        lines = [
            f"### {aid}",
            "",
        ]
        order = (
            "agent",
            "action",
            "action_type",
            "reason",
            "detail",
            "gate",
            "repo_id",
            "file_path",
            "risk_level",
            "status",
            "created_at",
        )
        shown = set()
        for k in order:
            v = spec.get(k)
            if v is not None and str(v).strip():
                lines.append(f"- **{k}:** {v}")
                shown.add(k)
        for k, v in sorted(spec.items()):
            if k in shown or k == "catalog_context":
                continue
            if v is not None and str(v).strip() and not isinstance(v, (dict, list)):
                lines.append(f"- **{k}:** {v}")
        cc = spec.get("catalog_context")
        if cc:
            lines.extend(["", "**Catalog context:**", "```", str(cc)[:4000], "```"])
        vr = spec.get("validation_reasons")
        if isinstance(vr, list) and vr:
            lines.extend(["", "**Validation notes:**", *[f"- {x}" for x in vr[:20]]])
        log_event("approval_explain", session_id=session_id, approval_id=aid)
        return {"reply": "\n".join(lines), "approval_request": None}

    if intent == "approval":
        pending = list_pending()
        if not pending:
            return {"reply": "No pending approvals.", "approval_request": None}
        ids = [p[0] for p in pending]
        return {"reply": f"Pending approvals: {ids}. Say 'approve <id>' or 'deny <id>'.", "approval_request": None}

    def _trace_execute(session_id: str, message: str, intent: str, action: str, outcome: str) -> None:
        log_event(
            "turn_trace",
            session_id=session_id,
            message=message[:200],
            intent=intent,
            sources_used="",
            proposals_created=1,
            execution_attempted=True,
            outcome=outcome,
            tool=action,
        )

    if intent == "execute_proposal":
        pending = session_state.get_pending_proposal(session_id)
        if not pending:
            log_event(
                "turn_trace",
                session_id=session_id,
                message=message[:200],
                intent=intent,
                sources_used="",
                proposals_created=0,
                execution_attempted=True,
                outcome="no_pending",
            )
            return {"reply": "No pending action to run. Ask for a scan or a recommendation first, then say 'do it'.", "approval_request": None}
        action = pending.get("action")
        args = pending.get("args") or {}
        log_event("execute_proposal", session_id=session_id, action=action, args=args)
        action_guard = evaluate_action(
            action=str(action or ""),
            tool_name=str(pending.get("tool") or ""),
            approved=False,
            fail_closed_on_missing_metadata=True,
        )
        if action_guard.requires_approval:
            session_state.clear_pending_proposal(session_id)
            _trace_execute(session_id, message, intent, str(action or ""), "approval_required")
            return {
                "reply": (
                    f"Action `{action}` is approval-gated and cannot execute via `do it` without an approval record. "
                    "Use the approval flow (`approve <id>`) or queue a controlled approval first."
                ),
                "approval_request": None,
            }
        if not action_guard.allowed:
            session_state.clear_pending_proposal(session_id)
            _trace_execute(session_id, message, intent, str(action or ""), "blocked")
            return {
                "reply": f"Blocked by approval policy: {action_guard.reason}.",
                "approval_request": None,
            }
        if action == "repo_search":
            query = args.get("query") or pending.get("query") or pending.get("target") or "sales script growflow"
            matches = repo_search_mod.search_repos(query, max_results=10)
            session_state.clear_pending_proposal(session_id)
            if not matches:
                _trace_execute(session_id, message, intent, action, "no_matches")
                return {"reply": f"No matches for \"{query}\" in repos. Try a different search or run a full repo scan.", "approval_request": None}
            lines = [f"- **{m['path']}** (score {m['score']}) — {m['why']}" for m in matches[:8]]
            reply = f"**Search results for \"{query}\":**\n\n" + "\n".join(lines)
            best = matches[0]
            session_state.set_pending_proposal(session_id, ProposalRecord(
                action="patch_registry",
                title="Update script registry",
                description=f"Update registry to use {best['path']} for the missing script.",
                tool=None,
                args={"target": best["path"], "detail": f"Update registry to use {best['path']} for the missing script."},
                approval_required=True,
                expires_after_turns=3,
            ))
            reply += "\n\n**Suggested next step:** Update the script registry to point to the best match above. Say 'approve' to apply, or ask to search for something else."
            _trace_execute(session_id, message, intent, action, "success")
            return {"reply": reply, "approval_request": None}
        if action in ("set_process_priority", "process_priority"):
            from brain.hardware.control.process_priority import set_process_priority as do_set_priority
            pid = args.get("pid")
            nice = args.get("nice", 10)
            if pid is None:
                session_state.clear_pending_proposal(session_id)
                _trace_execute(session_id, message, intent, action, "missing_args")
                return {"reply": "Process priority change requires a pid in the proposal args. Ask for hardware status to see top processes, then propose again with a pid.", "approval_request": None}
            try:
                pid = int(pid)
            except (TypeError, ValueError):
                session_state.clear_pending_proposal(session_id)
                _trace_execute(session_id, message, intent, action, "invalid_args")
                return {"reply": f"Invalid pid: {pid}. Must be an integer.", "approval_request": None}
            result = do_set_priority(pid, nice)
            session_state.clear_pending_proposal(session_id)
            if result.get("ok"):
                log_event("resource_control_applied", session_id=session_id, action="set_process_priority", pid=pid, nice=nice)
                _trace_execute(session_id, message, intent, action, "success")
                return {"reply": f"Set process {pid} priority (nice={nice}). The process will use less CPU when the system is busy.", "approval_request": None}
            _trace_execute(session_id, message, intent, action, "failed")
            return {"reply": f"Could not set process priority: {result.get('error', 'unknown')}.", "approval_request": None}
        if action in ("set_cpu_affinity", "cpu_affinity"):
            from brain.hardware.control.cpu_affinity import set_cpu_affinity as do_set_affinity
            pid = args.get("pid")
            cores = args.get("cores")
            if pid is None:
                session_state.clear_pending_proposal(session_id)
                _trace_execute(session_id, message, intent, action, "missing_args")
                return {"reply": "CPU affinity change requires a pid in the proposal args. Ask for hardware status to see top processes, then propose again with a pid.", "approval_request": None}
            if not cores:
                session_state.clear_pending_proposal(session_id)
                _trace_execute(session_id, message, intent, action, "missing_args")
                return {"reply": "CPU affinity change requires a 'cores' list (e.g. [4,5,6,7]) in the proposal args.", "approval_request": None}
            try:
                pid = int(pid)
                cores = list(cores) if isinstance(cores, (list, tuple)) else [int(cores)]
            except (TypeError, ValueError):
                session_state.clear_pending_proposal(session_id)
                _trace_execute(session_id, message, intent, action, "invalid_args")
                return {"reply": f"Invalid pid or cores: pid={pid}, cores={cores}. Must be integers.", "approval_request": None}
            result = do_set_affinity(pid, cores)
            session_state.clear_pending_proposal(session_id)
            if result.get("ok"):
                log_event("resource_control_applied", session_id=session_id, action="set_cpu_affinity", pid=pid, cores=cores)
                _trace_execute(session_id, message, intent, action, "success")
                return {"reply": f"Set process {pid} to run on cores {cores}.", "approval_request": None}
            _trace_execute(session_id, message, intent, action, "failed")
            return {"reply": f"Could not set CPU affinity: {result.get('error', 'unknown')}.", "approval_request": None}
        if action in ("worker_n8n_trigger", "n8n_trigger"):
            from brain.worker_clients import worker_n8n_trigger
            workflow_id = args.get("workflow") or args.get("workflow_id") or "default"
            payload = args.get("payload") or {}
            result = worker_n8n_trigger(workflow_id, payload, worker_name="worker-rig-01")
            session_state.clear_pending_proposal(session_id)
            if result.get("status") == "ok":
                _trace_execute(session_id, message, intent, action, "success")
                return {"reply": f"Triggered n8n workflow **{workflow_id}** on the worker.", "approval_request": None}
            _trace_execute(session_id, message, intent, action, "failed")
            return {"reply": f"n8n trigger failed: {result.get('error', 'unknown')}.", "approval_request": None}
        session_state.clear_pending_proposal(session_id)
        _trace_execute(session_id, message, intent, action, "not_implemented")
        return {"reply": f"Proposed action \"{action}\" is not yet implemented for 'do it'. Use approve <id> for queued approvals.", "approval_request": None}

    if intent == "repo_search":
        query = params.get("query")
        if not query:
            failure = session_state.get_last_failure(session_id)
            if failure:
                intent_name = failure.get("intent", "")
                path = failure.get("path", "")
                if "growflow" in intent_name.lower() or "growflow" in path.lower():
                    query = "growflow sales"
                else:
                    query = path.split("/")[-1] if path else "script"
            else:
                query = "script"
        matches = repo_search_mod.search_repos(query, max_results=10)
        if not matches:
            return {"reply": f"No matches for \"{query}\" in repos. Try 'scan my repos' for a full overview.", "approval_request": None}
        lines = [f"- **{m['path']}** (score {m['score']}) — {m['why']}" for m in matches[:8]]
        reply = f"**Search results for \"{query}\":**\n\n" + "\n".join(lines)
        session_state.update_active_topic(session_id, "registry_patch_proposal")
        best = matches[0]
        session_state.set_pending_proposal(session_id, ProposalRecord(
            action="patch_registry",
            title="Update script registry",
            description=f"Update registry to use {best['path']}.",
            tool=None,
            args={"target": best["path"], "detail": f"Update registry to use {best['path']}"},
            approval_required=True,
            expires_after_turns=3,
        ))
        reply += "\n\n**Suggested next steps:**\n1. Update `registry/scripts.json` to point the script path to the best match above.\n2. Run the command again to test. (Registry edits require manual change or approval.)"
        return {"reply": reply, "approval_request": None}

    if intent == "run_agent" and params.get("agent") == "repo_cartographer":
        try:
            repo_name = (params.get("repo_name") or "repos_root").strip() or "repos_root"
            worker_cfg = get_worker_ssh_config()
            if worker_cfg:
                path = worker_cfg["ai_lab_path"]
                inline = (
                    f"cd {path} && PYTHONPATH={path} python3 -c "
                    "'import json,sys; from pathlib import Path; sys.path.insert(0,\".\"); "
                    "from agents.repo_cartographer.cartographer import run_scan_to_dict; "
                    "name=sys.argv[1] if len(sys.argv)>1 else \"repos_root\"; "
                    "root=Path(\"repos_mirror\")/name; "
                    "d=run_scan_to_dict(root,name); "
                    "print(json.dumps(d) if d else \"\")' " + repo_name
                )
                res = run_ssh_command(
                    worker_cfg["host"],
                    inline,
                    user=worker_cfg.get("user"),
                    timeout_sec=90,
                )
                if res.returncode != 0:
                    return {"reply": f"Worker SSH error: {res.stderr or res.stdout or 'non-zero exit'}", "approval_request": None}
                out_str = (res.stdout or "").strip()
                if not out_str:
                    return {"reply": "Worker returned no summary (path may not exist on worker).", "approval_request": None}
                summary = json.loads(out_str)
                out_dir = _root / "summaries" / "repos"
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / f"{repo_name}.json"
                with open(out_path, "w") as f:
                    json.dump(summary, f, indent=2)
                artifacts = [
                    {"type": "repo_scan", "path": str(out_path), "summary_path": str(out_dir / f"{repo_name}_summary.md")},
                ]
                session_state.update_after_tool(
                    session_id, "repo_scan", "ok",
                    artifacts=artifacts,
                    summary={"repos_scanned": 1, "repo_name": repo_name, "top_findings": []},
                )
                return {"reply": f"Repo scan (worker) done. Wrote {out_path}", "approval_request": None}
            # Local: structured scan + session update
            cartographer_path = _root / "agents" / "repo_cartographer" / "cartographer.py"
            if cartographer_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("cartographer", cartographer_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                run_scan_structured = getattr(mod, "run_scan_structured", None)
            else:
                run_scan_structured = getattr(
                    __import__("agents.repo_cartographer.cartographer", fromlist=["run_scan_structured"]),
                    "run_scan_structured",
                    None,
                )
            if run_scan_structured:
                scan_root = _root / "repos_mirror"
                if not scan_root.exists():
                    scan_root = _root.parent
                struct = run_scan_structured(scan_root, name=repo_name if (scan_root / repo_name).exists() else "repos_root")
                if struct:
                    arts = struct.get("artifacts", [])
                    json_path = arts[0]["path"] if arts else None
                    md_path = next((a["path"] for a in arts if a.get("type") == "markdown"), None) if arts else None
                    session_state.update_after_tool(
                        session_id, "repo_scan", "ok",
                        artifacts=[{"type": "repo_scan", "path": json_path, "summary_path": md_path}],
                        summary=struct.get("summary"),
                    )
                    top = struct.get("summary", {}).get("top_findings", [])
                    reply = f"Repo scan done. Wrote {struct['artifacts'][0]['path']}"
                    if top:
                        reply += "\n\n**Top findings:**\n" + "\n".join(f"- {f}" for f in top[:5])
                    session_state.update_active_topic(session_id, "repo_scan_analysis")
                    reply += "\n\n**Suggested next steps:**\n1. Say \"what did the scan tell you\" for a summary.\n2. Say \"find it in repos\" or \"search repos for &lt;term&gt;\" to find a specific script or file.\n3. Fix missing READMEs or entrypoints in the repos listed above."
                    failure = session_state.get_last_failure(session_id)
                    if failure and "growflow" in str(failure.get("intent", "")).lower():
                        session_state.update_active_topic(session_id, "growflow_sales_failure")
                        session_state.set_pending_proposal(session_id, ProposalRecord(
                            action="repo_search",
                            title="Search repos for GrowFlow sales script",
                            description="Find the missing GrowFlow sales entrypoint in repos.",
                            tool="repo_search",
                            args={"query": "growflow sales"},
                            approval_required=False,
                            expires_after_turns=3,
                        ))
                        reply += "\n4. Say **do it** to search repos for the GrowFlow sales script."
                    return {"reply": reply, "approval_request": None}
            # Fallback: legacy run_scan
            if cartographer_path.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location("cartographer", cartographer_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                run_scan = mod.run_scan
            else:
                from agents.repo_cartographer.cartographer import run_scan
            scan_root = _root / "repos_mirror"
            if not scan_root.exists():
                scan_root = _root.parent
            out = run_scan(scan_root, name=repo_name if (scan_root / repo_name).exists() else "repos_root")
            return {"reply": f"Repo scan done. {out}", "approval_request": None}
        except Exception as e:
            return {"reply": f"Cartographer error: {e}", "approval_request": None}

    if intent == "scan_results":
        last = session_state.get_last_scan_artifact(session_id)
        if not last:
            return {"reply": "No scan results in this session. Run a repo scan first (e.g. \"scan my repos\").", "approval_request": None}
        path = last.get("path") or last.get("summary_path")
        summary_path = last.get("summary_path")
        content = _load_artifact_content(summary_path or path)
        if not content:
            content = _load_artifact_content(path)
        if not content:
            return {"reply": f"Could not read scan artifact at {path}. File may have been moved.", "approval_request": None}
        base_url = (llm_base_url or os.environ.get("LLM_BASE_URL") or _DEFAULT_LLM_BASE_URL).strip()
        model = (llm_model or os.environ.get("LLM_MODEL") or _DEFAULT_LLM_MODEL).strip()
        if base_url and len(content) > 500:
            system_content = (
                "You are the Command Center assistant. The user asked for a summary of the latest repo scan. "
                "Below is the actual scan output. Summarize what it says: what was scanned, main findings, and 1–3 concrete next steps. "
                "Do not invent findings. Only report what is in the provided content. Be concise."
            )
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": f"Scan output:\n\n{content[:8000]}"},
            ]
            model_reply = chat_completion(base_url, model, messages, stream_delta=stream_delta)
            if model_reply:
                session_state.update_active_topic(session_id, "repo_scan_analysis")
                model_reply += "\n\n**Suggested next steps:**\n1. Say \"find it in repos\" to search for a specific script.\n2. Fix the issues listed above (README, tests, entrypoints).\n3. Say **do it** to run a repo search if you had a recent failure (e.g. missing GrowFlow script)."
                return {"reply": model_reply, "approval_request": None}
        reply = "**Latest scan summary:**\n\n" + content[:4000]
        if len(content) > 4000:
            reply += "\n\n_(truncated)_"
        reply += "\n\n**Suggested next steps:**\n1. Search repos for a script (e.g. \"search repos for growflow\").\n2. Update registry or fix findings above."
        return {"reply": reply, "approval_request": None}

    # Worker health (Guru §26)
    if intent == "worker_health":
        try:
            from brain.worker_health import get_worker_health_snapshot

            timeout_budget_ms = 2000
            snap = get_worker_health_snapshot(
                "worker-rig-01",
                timeout_budget_ms=timeout_budget_ms,
                interactive=True,
            )
            log_event("worker_health_check", session_id=session_id, all_ok=snap.all_ok, services=[s.name for s in snap.services])
            tunnel = snap.tunnel_status or {}
            if snap.all_ok and tunnel.get("likely_up"):
                reply = f"Worker **{snap.worker_name}** is up through the current local tunnel. Worker Assistant is healthy, n8n is reachable, and Ollama is responding."
            elif snap.all_ok:
                reply = f"Worker **{snap.worker_name}** services are responding. Tunnel status: {tunnel.get('detail', 'unknown')}."
            else:
                parts = [
                    f"Worker **{snap.worker_name}** is unreachable/degraded for interactive budget checks.",
                    "",
                    f"- `worker_status`: `{snap.worker_status or 'offline_or_unreachable'}`",
                    f"- `checked_at`: `{snap.checked_at}`",
                    f"- `timeout_budget_ms`: `{snap.timeout_budget_ms or timeout_budget_ms}`",
                ]
                if snap.last_known_status:
                    parts.append(f"- `last_known_status`: `{snap.last_known_status.get('worker_status', 'unknown')}` at `{snap.last_known_status.get('checked_at', 'unknown')}`")
                for s in snap.services:
                    parts.append(f"- **{s.name}**: {'ok' if s.ok else s.detail}")
                parts.append("\nLikely causes: tunnel down for some ports, or worker services not running. Check the tunnel command, then run the worker validation script.")
                reply = "\n".join(parts)
            run_timer.segment("worker_health")
            _write_turn_trace_if_enabled(
                write=write_response_trace,
                req_id=req_id,
                session_id=session_id,
                user_message=msg,
                route="worker_health",
                model="",
                worker_used=True,
                run_timer=run_timer,
                extra_stage_timings_ms={},
                first_token_ms=first_token_elapsed(),
                first_token_wall_ms=first_token_wall_ms[0],
                receive_wall_ms=receive_wall_ms,
                client_submit_epoch_ms=client_submit_epoch_ms,
                evidence_count=0,
                sources_used=["worker_health_snapshot"],
                fallback_reason=None,
                final_answer_type="worker_health",
                reply_preview=reply,
                final_answer_source="tool",
            )
            return {"reply": reply, "approval_request": None}
        except Exception as e:
            log_event("worker_health_check", session_id=session_id, all_ok=False, error=str(e))
            return {"reply": f"Could not check worker health: {e}. Ensure WORKER_ASSISTANT_URL / WORKER_N8N_URL / OLLAMA_HOST are set if using tunneled services.", "approval_request": None}

    # Worker Assistant: index repo, retrieve (Guru §26)
    if intent == "worker_index":
        try:
            from brain.worker_clients import worker_assistant_index_repo
            repo_path = (params.get("repo_path") or "repos_root").strip()
            out = worker_assistant_index_repo(repo_path, worker_name="worker-rig-01")
            if out.get("status") == "ok":
                log_event("worker_service_used", session_id=session_id, service="worker_assistant", action="index_repo")
                return {"reply": f"Worker Assistant indexed repo **{repo_path}**.", "approval_request": None}
            return {"reply": f"Worker Assistant index failed: {out.get('error', 'unknown')}.", "approval_request": None}
        except Exception as e:
            return {"reply": f"Worker index error: {e}.", "approval_request": None}

    if intent == "worker_retrieve":
        try:
            from brain.worker_clients import worker_assistant_retrieve
            query = (params.get("query") or message or "summary").strip()[:500]
            out = worker_assistant_retrieve(query, worker_name="worker-rig-01")
            if out.get("status") == "ok":
                data = out.get("data") or {}
                text = data.get("text") or data.get("answer") or str(data)[:500]
                log_event("worker_service_used", session_id=session_id, service="worker_assistant", action="retrieve")
                return {"reply": f"Worker Assistant: {text}", "approval_request": None}
            return {"reply": f"Worker retrieve failed: {out.get('error', 'unknown')}.", "approval_request": None}
        except Exception as e:
            return {"reply": f"Worker retrieve error: {e}.", "approval_request": None}

    # Trigger n8n workflow: set pending proposal; user says "do it" to execute (Guru §26)
    if intent == "trigger_workflow":
        workflow_id = (params.get("workflow_id") or "default").strip()
        session_state.set_pending_proposal(session_id, ProposalRecord(
            action="worker_n8n_trigger",
            title=f"Trigger n8n workflow: {workflow_id}",
            description=f"Trigger workflow **{workflow_id}** on the worker. Requires approval.",
            tool="worker_n8n_trigger",
            args={"workflow": workflow_id, "payload": {}},
            approval_required=True,
            expires_after_turns=3,
        ))
        return {"reply": f"Proposed: trigger n8n workflow **{workflow_id}** on the worker. Say **do it** to run (approval required).", "approval_request": None}

    # Ops overview (Guru §23) — deterministic local answer (no LLM required)
    if intent == "ops_overview":
        try:
            from brain import ops_registry

            text = ops_registry.get_ops_summary_text_cached()
            reply = "### Operations registry (systems / workers / automations)\n\n" + text
            run_timer.segment("ops_overview")
            _write_turn_trace_if_enabled(
                write=write_response_trace,
                req_id=req_id,
                session_id=session_id,
                user_message=msg,
                route="ops_overview",
                model="",
                worker_used=False,
                run_timer=run_timer,
                extra_stage_timings_ms={},
                first_token_ms=first_token_elapsed(),
                first_token_wall_ms=first_token_wall_ms[0],
                receive_wall_ms=receive_wall_ms,
                client_submit_epoch_ms=client_submit_epoch_ms,
                evidence_count=1,
                sources_used=["ops_registry"],
                fallback_reason=None,
                final_answer_type="ops_overview",
                reply_preview=reply,
                final_answer_source="tool",
            )
            return {"reply": reply, "approval_request": None}
        except Exception as e:
            return {"reply": f"Could not load ops registry: {e}", "approval_request": None}

    # Default: answer — use grounded response pipeline (Guru §21) when available
    base_url = (llm_base_url or os.environ.get("LLM_BASE_URL") or _DEFAULT_LLM_BASE_URL).strip()
    model = (llm_model or os.environ.get("LLM_MODEL") or _DEFAULT_LLM_MODEL).strip()
    # Benchmark / CI: skip remote LLM calls (set AI_LAB_ORCH_NO_LLM=1).
    if os.environ.get("AI_LAB_ORCH_NO_LLM", "").strip() == "1":
        base_url = ""
    rules = _load_workflow_rules()
    rr_context = ""
    if rules:
        rr_rules = [r for r in rules if r.get("mode") == "RR" and (r.get("summary") or r.get("rule"))]
        if rr_rules:
            lines = [r.get("summary") or r.get("rule", "")[:200] for r in rr_rules[:5]]
            rr_context = "Active RR rules: " + "; ".join(lines)

    routing_reason = ""
    answer_style = ""
    proposals_list: list = []
    g_timings: dict[str, float] = {}
    ev_count = 0
    src_used: list[str] = []
    llm_extra: dict[str, float] = {}
    try:
        grounded = build_grounded_response(
            session_id=session_id,
            message=message,
            intent=intent,
            entities=[],
        )
        run_timer.segment("build_grounded_response_total")
        evidence_block = grounded.get("evidence_block", "")
        proposals_suffix = grounded.get("proposals_suffix", "")
        proposals_list = grounded.get("proposals") or []
        answer_style = grounded.get("answer_style", "")
        routing_reason = grounded.get("routing_reason", "") or ""
        g_timings = grounded.get("stage_timings_ms") or {}
        ev_count = int(grounded.get("evidence_count") or 0)
        src_used = list(grounded.get("sources_used") or [])
        # Hard insufficient_evidence override (Guru §24.13): do not call LLM; return fixed no-evidence reply.
        # Catalog may still be prepended to evidence_block for the model path, but it is not proof of session facts—
        # do not skip this stop based on catalog text alone (that led to empty LLM + generic [Orchestrator] fallback).
        if answer_style == "insufficient_evidence":
            log_event("insufficient_evidence_override", session_id=session_id, intent=intent)
            log_event(
                "turn_trace",
                session_id=session_id,
                message=message[:200],
                intent=intent,
                sources_used=(routing_reason[:100] if routing_reason else ""),
                proposals_created=len(proposals_list),
                execution_attempted=False,
                outcome="insufficient_evidence",
            )
            cat_hint = ""
            try:
                from brain.catalog_loader import format_catalog_grounding_for_message

                cat_hint = format_catalog_grounding_for_message(message) or ""
            except Exception:
                cat_hint = ""
            reply = (
                "I don’t have **session-specific evidence** loaded for that yet (no recent scan output, "
                "registry snapshot, or tool result in memory).\n\n"
                "**What you can do next:** try **ops overview** / **what systems are active?**, run **scan my repos**, "
                "or ask **check worker health**. For factual POS numbers, use **sales today** or Growflow scripts.\n\n"
                "If this was meant as a general question, rephrase without requiring private data."
            )
            if cat_hint:
                reply = cat_hint + "\n\n---\n\n" + reply
            if proposals_suffix:
                reply = reply + proposals_suffix
            _write_turn_trace_if_enabled(
                write=write_response_trace,
                req_id=req_id,
                session_id=session_id,
                user_message=msg,
                route=intent,
                model=model,
                worker_used=False,
                run_timer=run_timer,
                extra_stage_timings_ms=dict(g_timings),
                first_token_ms=first_token_elapsed(),
                first_token_wall_ms=first_token_wall_ms[0],
                receive_wall_ms=receive_wall_ms,
                client_submit_epoch_ms=client_submit_epoch_ms,
                evidence_count=ev_count,
                sources_used=src_used,
                fallback_reason="insufficient_evidence_hard_stop",
                final_answer_type="insufficient_evidence",
                reply_preview=reply,
                final_answer_source="retrieval",
            )
            return {"reply": reply, "approval_request": None}
        # Set pending proposal for first executable hardware control so "do it" works (Guru §25)
        for p in proposals_list:
            if getattr(p, "action", None) in ("set_process_priority", "process_priority", "set_cpu_affinity", "cpu_affinity"):
                args = getattr(p, "args", None) or {}
                if args.get("pid") is not None:
                    session_state.set_pending_proposal(session_id, p)
                    break
    except Exception:
        evidence_block = ""
        proposals_suffix = ""
        answer_style = ""
        routing_reason = ""
        needs_web = source_selection.detect_freshness(msg)
        session_context = {"message": msg, "session_id": session_id}
        sources = source_selection.select_sources(intent, needs_web, session_context)
        from brain.tools.time_context import get_time_context
        tz = session_state.get_user_timezone(session_id)
        tc = get_time_context(tz)
        time_context = f"Current date/time: {tc.get('current_datetime', '')} ({tc.get('timezone', tz)})."
        msg_lower = msg.lower()
        evidence_triggers = (
            "scan", "result", "report", "output", "improvement", "what did", "that scan", "the scan",
            "findings", "issues", "analysis", "summary", "problems", "what's wrong", "what changed",
        )
        if any(w in msg_lower for w in evidence_triggers):
            last = session_state.get_last_scan_artifact(session_id)
            if last:
                path = last.get("summary_path") or last.get("path")
                content = _load_artifact_content(path)
                if content:
                    evidence_block = f"\n\nLatest scan artifact (use this to answer; do not invent):\n---\n{content[:6000]}\n---"
        if "weather" in msg_lower:
            from brain.tools.weather_context import get_weather_evidence_text
            evidence_block += get_weather_evidence_text(msg)
        elif "web" in sources:
            words = [w for w in msg.split() if len(w) > 2][:5]
            query = " ".join(words) if words else msg[:80]
            web_results = web_tool.web_search(query, max_results=5, timeout_sec=6.0)
            if web_results:
                evidence_block += "\n\nWeb search results:\n---\n" + "\n".join(
                    f"- [{r.get('title', '')}]({r.get('url', '')}): {r.get('snippet', '')[:200]}" for r in web_results
                ) + "\n---"
        if time_context and ("local" in sources or "web" in sources):
            evidence_block += f"\n\n{time_context}"

    # Short catalog shouts: local LLMs often refuse despite in-context catalog; answer deterministically.
    if intent == "answer":
        try:
            from brain.catalog_loader import format_component_grounding, matching_components

            mstrip = (msg or "").strip()
            if mstrip and len(mstrip) <= 160 and "?" not in mstrip:
                comps = matching_components(msg)
                if comps:
                    reply = "From the **lab system catalog** (authoritative):\n\n" + "\n\n".join(
                        format_component_grounding(c) for c in comps[:4]
                    )
                    if routing_reason:
                        reply += "\n\n_Used: " + (
                            routing_reason.split(".")[0] if "." in routing_reason else routing_reason
                        ) + "._"
                    log_event(
                        "turn_trace",
                        session_id=session_id,
                        message=msg[:200],
                        intent=intent,
                        answer_style=answer_style or "catalog_deterministic",
                        routing_reason=(routing_reason[:150] if routing_reason else ""),
                        sources_used=(routing_reason[:100] if routing_reason else ""),
                        proposals_created=len(proposals_list),
                        proposal_actions=[getattr(p, "action", None) for p in proposals_list[:5]]
                        if proposals_list
                        else [],
                        execution_attempted=False,
                        outcome="catalog_deterministic",
                    )
                    return {"reply": reply, "approval_request": None}
        except Exception:
            pass

    fallback = (
        f"[Orchestrator] Intent: {intent}. Say 'run script X', 'sales today', 'scan repo', or 'approve/deny'."
    )
    if rr_context:
        fallback += "\n\n**" + rr_context + "**"

    reply = fallback
    if base_url:
        system_content = (
            "You are the Command Center assistant. You help with running scripts, repo scans, "
            "approvals, and general questions. Be concise. When the user asks for something we can do "
            "(e.g. sales today, scan a repo, run a script), we do it automatically—reply naturally and "
            "confirm what was done; don't ask them to use a specific phrase. "
            "If the user asks about the result of a script, scan, report, or artifact: do not answer from general knowledge. "
            "Only use the evidence provided in this conversation (e.g. scan output below). "
            "If key evidence is **(none)** or clearly insufficient for a precise factual claim, still give a **short useful reply**: "
            "what is missing, 1–3 concrete next actions (e.g. run scan, ops overview, check worker), and what you *can* say safely. "
            "Do **not** refuse the whole question with a generic 'insufficient evidence' unless the user demands exact numbers or secrets you truly lack."
        )
        try:
            from brain.catalog_loader import format_catalog_grounding_for_message

            _cat_sys = format_catalog_grounding_for_message(message)
            if _cat_sys:
                system_content += "\n\n" + _cat_sys
        except Exception:
            pass
        if rr_context:
            system_content += "\n\n" + rr_context
        user_content = message + evidence_block
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]
        run_timer.segment("before_llm_call")
        llm_timer = StageTimer()
        model_reply = chat_completion(
            base_url,
            model,
            messages,
            stream_delta=stream_delta,
            on_first_token=_mark_first_token,
        )
        llm_timer.segment("llm_call_complete")
        llm_extra = dict(llm_timer.segments_ms)
        if model_reply:
            reply = model_reply
            # Local LLMs often ignore catalog grounding and still refuse; substitute facts.
            # Use matching_components (not evidence_block text) so this works even if grounding threw
            # and fell back to a sparse evidence_block.
            if intent == "answer":
                rlow = reply.lower()
                if "insufficient" in rlow and "evidence" in rlow:
                    try:
                        from brain.catalog_loader import format_component_grounding, matching_components

                        comps = matching_components(message)
                        if comps:
                            reply = "From the **lab system catalog** (authoritative):\n\n" + "\n\n".join(
                                format_component_grounding(c) for c in comps[:4]
                            )
                            log_event("catalog_reply_substitution", session_id=session_id, components=[c.get("id") for c in comps[:4]])
                    except Exception:
                        pass
    # Note: grounded templates legitimately contain "(none)" for topic/secondary; do not scan the whole header for that substring.
    if (
        not base_url
        and intent == "answer"
        and evidence_block
        and len(evidence_block.strip()) > 120
        and "\nKey Evidence:\n(none)" not in evidence_block
    ):
        reply = (
            "_No LLM configured (`LLM_BASE_URL` empty or `AI_LAB_ORCH_NO_LLM=1`) — **local evidence only**:_\n\n"
            + evidence_block[:14000]
        )
    if reply == fallback:
        try:
            from brain.catalog_loader import format_catalog_grounding_for_message

            _fb_cat = format_catalog_grounding_for_message(message)
            if _fb_cat:
                reply = f"{_fb_cat}\n\n{reply}"
        except Exception:
            pass
    if proposals_suffix and reply != fallback:
        reply = reply + proposals_suffix

    # Guru §24.14: transparency line (Used / Reason)
    if routing_reason:
        reply = reply + "\n\n_Used: " + (routing_reason.split(".")[0] if "." in routing_reason else routing_reason) + "._"
    # Per-turn trace (Guru §24.14): full fields for reconstruction
    log_event(
        "turn_trace",
        session_id=session_id,
        message=msg[:200],
        intent=intent,
        answer_style=answer_style,
        routing_reason=(routing_reason[:150] if routing_reason else ""),
        sources_used=(routing_reason[:100] if routing_reason else ""),
        proposals_created=len(proposals_list),
        proposal_actions=[getattr(p, "action", None) for p in proposals_list[:5]] if proposals_list else [],
        execution_attempted=False,
        outcome="answer",
    )

    merged_timings = dict(g_timings)
    merged_timings.update(llm_extra)
    fb = "orchestrator_fallback" if reply.strip().startswith("[Orchestrator]") else None
    if fb:
        final_src = "orchestrator_fallback"
    elif base_url:
        final_src = "model"
    elif evidence_block and "\nKey Evidence:\n(none)" not in evidence_block:
        final_src = "retrieval"
    else:
        final_src = "tool"
    _write_turn_trace_if_enabled(
        write=write_response_trace,
        req_id=req_id,
        session_id=session_id,
        user_message=msg,
        route=intent,
        model=model,
        worker_used=False,
        run_timer=run_timer,
        extra_stage_timings_ms=merged_timings,
        first_token_ms=first_token_elapsed(),
        first_token_wall_ms=first_token_wall_ms[0],
        receive_wall_ms=receive_wall_ms,
        client_submit_epoch_ms=client_submit_epoch_ms,
        evidence_count=ev_count,
        sources_used=src_used,
        fallback_reason=fb,
        final_answer_type=(answer_style or "llm_answer")[:80],
        reply_preview=reply,
        final_answer_source=final_src,
    )

    return {
        "reply": reply,
        "approval_request": None,
    }


if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "Hello"
    out = run(msg)
    print(out["reply"])
    if out.get("approval_request"):
        print("Approval:", out["approval_request"])
