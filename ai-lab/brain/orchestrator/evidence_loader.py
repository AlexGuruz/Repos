"""
Evidence loader (Guru §21). Loads sources selected by router into LoadedEvidence.
"""
from __future__ import annotations

from pathlib import Path

from brain.schemas.routing import RoutingDecision
from brain.schemas.evidence import LoadedEvidence, EvidenceItem


def _read_file(path: str, max_chars: int = 12000) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    try:
        p = Path(path)
        if not p.exists():
            return None, [f"Path not found: {path}"]
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > max_chars:
            content = content[:max_chars]
            notes.append(f"Content truncated to {max_chars} chars")
        return content, notes
    except Exception as e:
        return None, [str(e)]


def load_evidence(decision: RoutingDecision, session_id: str) -> LoadedEvidence:
    """
    Load evidence according to routing decision. Uses session_state to resolve artifact paths.
    """
    from brain import session_state

    session = session_state.get(session_id)
    out = LoadedEvidence(session_context=dict(session))
    all_notes: list[str] = []

    # Local targets: artifact paths from decision or from session last_artifacts
    for target in decision.local_targets:
        if target.kind == "artifact" and target.path:
            content, notes = _read_file(target.path)
            all_notes.extend(notes)
            if content:
                out.local_evidence.append(EvidenceItem(
                    source_type="markdown_summary" if target.path.endswith(".md") else "json_artifact",
                    path=target.path,
                    content=content,
                    weight=target.priority,
                ))
        elif target.kind == "failure_record":
            failure = session.get("last_failure")
            if failure:
                from brain.failure_analysis import analyze_failure
                reason = failure.get("reason") or failure.get("failure_reason") or str(failure)
                intent = failure.get("intent") or ""
                path = failure.get("path") or ""
                analyzed = analyze_failure(reason, intent=intent, path=path)
                structured = (
                    f"Failure diagnosis — Category: {analyzed['category']}. "
                    f"Likely cause: {analyzed['likely_cause']} "
                    f"Suggested actions: {', '.join(analyzed['suggested_actions'])}."
                )
                out.local_evidence.append(EvidenceItem(
                    source_type="failure_record",
                    title="Last failure (diagnosed)",
                    content=structured,
                    metadata={**failure, "failure_analysis": analyzed},
                    weight=1.0,
                ))
        elif target.kind == "config" and target.path:
            content, notes = _read_file(target.path, max_chars=8000)
            all_notes.extend(notes)
            if content:
                out.local_evidence.append(EvidenceItem(
                    source_type="config",
                    path=target.path,
                    content=content,
                    weight=target.priority,
                ))
        elif target.kind == "hardware":
            try:
                from brain.hardware import get_snapshot
                from brain.hardware.telemetry import check_thresholds
                snapshot = get_snapshot()
                text = snapshot.to_assistant_text()
                alerts = check_thresholds(snapshot)
                if alerts:
                    text += "\n\nAlerts: " + "; ".join(alerts)
                out.local_evidence.append(EvidenceItem(
                    source_type="hardware_snapshot",
                    title="Current hardware state",
                    content=text,
                    metadata=snapshot.to_dict(),
                    weight=1.0,
                ))
            except Exception as e:
                all_notes.append(f"Hardware snapshot failed: {e}")
        elif target.kind == "ops_registry":
            try:
                from brain import ops_registry
                summary = ops_registry.get_ops_summary_text()
                out.local_evidence.append(EvidenceItem(
                    source_type="ops_registry",
                    title="Operations registry",
                    content=summary,
                    weight=1.0,
                ))
            except Exception as e:
                all_notes.append(f"Ops registry load failed: {e}")
        elif target.kind == "weather":
            try:
                from brain.tools.weather_context import fetch_weather_text
                text = fetch_weather_text(target.query)
                if text:
                    out.local_evidence.append(EvidenceItem(
                        source_type="weather_forecast",
                        title="Current weather (Open-Meteo)",
                        content=text,
                        metadata={"provider": "open-meteo"},
                        weight=1.0,
                    ))
                else:
                    all_notes.append("Weather fetch returned no data (network or geocoding).")
            except Exception as e:
                all_notes.append(f"Weather load failed: {e}")

    # If no local targets but needs_local and we have last_artifacts, load from session
    if decision.needs_local and not out.local_evidence:
        for a in session.get("last_artifacts") or []:
            if a.get("type") == "repo_scan":
                path = a.get("summary_path") or a.get("path")
                if path:
                    content, notes = _read_file(path)
                    all_notes.extend(notes)
                    if content:
                        out.local_evidence.append(EvidenceItem(
                            source_type="markdown_summary" if path.endswith(".md") else "json_artifact",
                            path=path,
                            content=content,
                            weight=1.0,
                        ))
                break

    # Web: loaded by caller and passed in, or load here via web_tool
    if decision.web_queries:
        from brain import web_tool
        for q in decision.web_queries[:2]:
            results = web_tool.web_search(q, max_results=5)
            for r in results:
                out.web_evidence.append(EvidenceItem(
                    source_type="web",
                    title=r.get("title"),
                    content=r.get("snippet"),
                    metadata={"url": r.get("url"), "retrieved_at": r.get("timestamp")},
                    weight=0.8,
                ))

    # Time context (PDR: use session user_timezone)
    if decision.needs_time:
        from brain.tools.time_context import get_time_context
        tz = session.get("user_timezone") or "America/Chicago"
        out.time_context = get_time_context(tz)

    out.notes = all_notes
    out.sufficient = len(out.local_evidence) > 0 or len(out.web_evidence) > 0 or bool(out.time_context)
    return out
