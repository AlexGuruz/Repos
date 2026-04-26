"""
Source router (Guru §21). Chooses minimum sufficient source mix (local, web, time, session).
"""
from __future__ import annotations

import os

from brain.schemas.routing import RoutingDecision, LocalTarget
from brain.orchestrator.freshness import FreshnessResult
from brain.orchestrator.session_resolution import SessionResolution
from brain.orchestrator.routing_policy import match_answer_fast_path


def _company_bi_summary_path() -> str | None:
    """Path to Company BI business summary (sales, inventory, expenses, payroll). Env COMPANY_BI_SUMMARY_PATH overrides."""
    path = (os.environ.get("COMPANY_BI_SUMMARY_PATH") or "").strip()
    if path:
        return path
    # Default: Growflow BI summary written by pipeline / BI_BUSINESS_SUMMARY.md
    default = "E:/Repos/Growflow/company_bi/docs/BI_BUSINESS_SUMMARY.md"
    return default


def route_sources(
    *,
    message: str,
    intent: str,
    entities: list[str],
    session: dict,
    freshness: FreshnessResult,
    resolved: SessionResolution,
) -> RoutingDecision:
    """
    Decide which evidence sources to gather. Returns RoutingDecision.
    Local-first for internal queries; web when external current truth needed; local+web for comparison.
    """
    msg = (message or "").lower()
    # Internal/system indicators -> local first
    internal_indicators = (
        "repo", "scan", "logs", "script", "config", "integration", "repos", "failure",
        "our system", "my repos", "registry", "documentation", "doc status", "docs status",
    )
    # External current -> web
    external_indicators = (
        "weather", "broker", "price", "docs", "law", "release", "patch notes", "current version",
    )
    # Comparison -> local + web
    comparison_indicators = ("still valid", "still current", "compare with current", "changed", "outdated", "matches latest")

    needs_local = False
    needs_web = False
    needs_time = freshness.needs_time
    local_targets: list[LocalTarget] = []
    web_queries: list[str] = []
    session_targets = ["active_topic"]
    reason = ""
    answer_style_hint = "direct_status"

    # Resolved artifact -> use it
    if resolved.resolved_artifact:
        path = resolved.resolved_artifact.get("summary_path") or resolved.resolved_artifact.get("path")
        if path:
            local_targets.append(LocalTarget(kind="artifact", path=path, priority=1, reason="resolved scan artifact"))
        needs_local = True
        session_targets.extend(["last_artifacts", "active_topic"])
        reason = "User is referring to the most recent scan in session."
        answer_style_hint = "summary_from_artifact"

    # Resolved failure -> use it
    elif resolved.resolved_failure:
        needs_local = True
        local_targets.append(LocalTarget(kind="failure_record", reason="resolved last failure"))
        session_targets.extend(["last_failure"])
        reason = "User is asking about the last failed action."
        answer_style_hint = "failure_explanation"

    # Ops overview (Guru §23 Phase 4)
    elif intent == "ops_overview":
        needs_local = True
        local_targets.append(LocalTarget(kind="ops_registry", reason="User asked for systems/workers/ops overview."))
        session_targets.extend(["active_topic"])
        reason = "Ops fabric: load systems, workers, automations from registry."
        answer_style_hint = "direct_status"

    # Hardware status (Guru §25)
    elif intent == "hardware_status":
        needs_local = True
        local_targets.append(LocalTarget(kind="hardware", reason="User asked about hardware/CPU/GPU state."))
        session_targets.extend(["active_topic"])
        reason = "Hardware observability: load current CPU/GPU/process metrics."
        answer_style_hint = "direct_status"

    # Company BI (Growflow: sales, inventory, expenses, payroll) — load BI summary for inference
    elif intent == "company_bi":
        needs_local = True
        bi_path = _company_bi_summary_path()
        if bi_path:
            local_targets.append(LocalTarget(
                kind="artifact",
                path=bi_path,
                priority=1,
                reason="User asked about business/sales/expenses/payroll/inventory; load Company BI summary.",
            ))
        session_targets.extend(["active_topic"])
        reason = "Company BI: load business summary (sales, inventory, expenses, payroll) for grounded answer."
        answer_style_hint = "summary_from_artifact"

    # Intent-based
    elif intent in ("run", "run_agent", "scan_results", "execute_proposal", "repo_search"):
        needs_local = True
        if resolved.resolved_artifact:
            path = resolved.resolved_artifact.get("summary_path") or resolved.resolved_artifact.get("path")
            if path:
                local_targets.append(LocalTarget(kind="artifact", path=path, priority=1))
        reason = f"Intent {intent} requires local evidence."
        if intent == "scan_results":
            answer_style_hint = "summary_from_artifact"

    # Answer intent: check message for external vs internal
    elif intent == "answer":
        fast = match_answer_fast_path(message)
        if fast is not None:
            needs_local = fast.needs_local
            needs_web = fast.needs_web
            local_targets.extend(list(fast.local_targets))
            reason = fast.reason
            answer_style_hint = fast.answer_style_hint
        elif any(x in msg for x in comparison_indicators):
            needs_local = True
            needs_web = True
            reason = "Comparison with current external state requested."
            answer_style_hint = "local_plus_web_comparison"
        # Time/date only ("what time is it") — local timezone; do not burn Tavily/Serper
        elif freshness.freshness_needed and freshness.needs_time and not any(x in msg for x in external_indicators):
            needs_web = False
            reason = "Local date/time only (no web search)."
            answer_style_hint = "direct_status"
        elif any(x in msg for x in external_indicators) and freshness.freshness_needed:
            if "weather" in msg:
                # Open-Meteo (free); no paid web search quota
                needs_local = True
                from brain.tools.weather_context import extract_location_hint

                hint = extract_location_hint(message)
                local_targets.append(LocalTarget(
                    kind="weather",
                    query=hint,
                    priority=1,
                    reason="Current weather via Open-Meteo (no Tavily/Serper).",
                ))
                reason = "Weather: Open-Meteo forecast for configured or extracted location."
                answer_style_hint = "direct_status"
            else:
                needs_web = True
                words = [w for w in message.split() if len(w) > 2][:5]
                web_queries.append(" ".join(words) if words else message[:80])
                reason = "Current external information requested."
                answer_style_hint = "direct_status"
        elif any(x in msg for x in internal_indicators) or resolved.resolved_artifact:
            needs_local = True
            if resolved.resolved_artifact:
                path = resolved.resolved_artifact.get("summary_path") or resolved.resolved_artifact.get("path")
                if path:
                    local_targets.append(LocalTarget(kind="artifact", path=path, priority=1))
            session_targets.extend(["last_artifacts", "last_failure"])
            reason = "Internal/system question or resolved artifact."
            if "look off" in msg or "should i do" in msg or "what do" in msg:
                answer_style_hint = "proposal_after_analysis"
        elif freshness.freshness_needed:
            needs_web = True
            web_queries.append(message[:80])
            reason = "Freshness triggers suggest current info needed."

    confidence = freshness.confidence if (needs_web or needs_time) else 0.85
    return RoutingDecision(
        intent=intent,
        needs_local=needs_local,
        needs_web=needs_web,
        needs_time=needs_time,
        needs_session=True,
        local_targets=local_targets,
        web_queries=web_queries,
        session_targets=list(dict.fromkeys(session_targets)),
        reason=reason or "Default routing.",
        confidence=confidence,
        answer_style_hint=answer_style_hint,
    )
