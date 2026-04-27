"""
Prepared context loading, freshness, and lightweight answer selection.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from brain.prepared_context.store import SNAPSHOT_NAMES, load_index, load_snapshot


def _iso_to_epoch(s: str | None) -> float | None:
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def is_snapshot_stale(snapshot: dict[str, Any]) -> bool:
    gen = _iso_to_epoch(snapshot.get("generated_at"))
    fresh = int(snapshot.get("freshness_seconds") or 0)
    if not gen or fresh <= 0:
        return True
    return (time.time() - gen) > fresh


def load_snapshot_fresh(snapshot_type: str) -> dict[str, Any] | None:
    snap = load_snapshot(snapshot_type)
    if not snap:
        return None
    snap["stale"] = is_snapshot_stale(snap)
    return snap


def load_all_snapshots() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in SNAPSHOT_NAMES:
        s = load_snapshot_fresh(name)
        if s:
            out[name] = s
    return out


def _pick_snapshots_for_message(msg: str) -> list[str]:
    m = (msg or "").lower()
    if any(k in m for k in ("systems are active", "system status", "what is running", "what is broken")):
        return ["system_snapshot"]
    if any(k in m for k in (
        "what changed recently",
        "repo status",
        "docs stale",
        "docs need cleanup",
        "repo docs status",
        "documentation cleanup status",
        "which readmes are stale",
        "explain repo documentation status",
    )):
        return ["repo_pulse", "system_snapshot"]
    if any(k in m for k in ("work on today", "what is next", "blocked", "daily plan", "project agenda")):
        return ["project_agenda", "repo_pulse"]
    if any(k in m for k in ("calendar", "reminder", "daily digest", "personal ops")):
        return ["personal_ops_snapshot"]
    if any(k in m for k in ("growflow status", "business", "inventory", "par")):
        return ["growflow_snapshot"]
    if any(k in m for k in ("worker", "ollama", "n8n", "offload")):
        return ["worker_snapshot"]
    return []


def _quality_gate(
    *,
    message: str,
    used: list[dict[str, Any]],
    missing: list[str],
    stale: bool,
    conf: float,
) -> tuple[float, dict[str, Any]]:
    msg_l = (message or "").lower()
    # Inputs requested by policy:
    # freshness, evidence breadth, source traceability, confidence reason,
    # broad question with narrow evidence, generated_at exposure for time-sensitive.
    freshness_score = 1.0 if not stale else 0.35
    breadth_sources = 0
    evidence_count = 0
    traceable_count = 0
    gen_present = 0
    for s in used:
        items = s.get("evidence_items") or []
        evidence_count += len(items)
        local_sources = {str(i.get("source_path_or_tool") or "").strip() for i in items if isinstance(i, dict)}
        local_sources = {x for x in local_sources if x}
        breadth_sources += len(local_sources)
        traceable_count += sum(1 for i in items if isinstance(i, dict) and str(i.get("source_path_or_tool") or "").strip())
        if s.get("generated_at"):
            gen_present += 1
    breadth_score = 0.4 if evidence_count <= 1 else (0.7 if evidence_count <= 3 else 1.0)
    traceability_score = 0.35 if traceable_count == 0 else (0.75 if traceable_count < 2 else 1.0)
    broad_markers = ("status", "summary", "summarize", "what changed", "what is broken", "overview")
    broad_q = any(k in msg_l for k in broad_markers)
    narrow_penalty = 0.2 if (broad_q and (evidence_count <= 1 or breadth_sources <= 1)) else 0.0
    time_sensitive = any(k in msg_l for k in ("now", "current", "today", "recent", "status"))
    generated_at_score = 1.0 if (not time_sensitive or gen_present == len(used)) else 0.45
    conf_score = max(0.0, min(1.0, conf))
    quality = (
        0.28 * freshness_score
        + 0.24 * breadth_score
        + 0.20 * traceability_score
        + 0.18 * conf_score
        + 0.10 * generated_at_score
        - narrow_penalty
    )
    quality = max(0.0, min(1.0, round(quality, 3)))
    reasons = {
        "freshness": freshness_score,
        "evidence_breadth": breadth_score,
        "source_traceability": traceability_score,
        "confidence_reason": conf_score,
        "broad_but_narrow_penalty": narrow_penalty,
        "generated_at_exposure": generated_at_score,
        "evidence_items_count": evidence_count,
        "missing_snapshots": list(missing),
        "broad_question": broad_q,
    }
    return quality, reasons


def try_prepared_context_answer(message: str, intent: str) -> dict[str, Any] | None:
    """Return prepared-context answer payload or None if not applicable."""
    if intent not in ("answer", "ops_overview", "worker_health", "company_bi"):
        return None
    wanted = _pick_snapshots_for_message(message)
    if not wanted:
        return None
    used: list[dict[str, Any]] = []
    missing: list[str] = []
    stale = False
    conf = 0.0
    started = time.perf_counter()
    for name in wanted:
        s = load_snapshot_fresh(name)
        if not s:
            missing.append(name)
            continue
        used.append(s)
        conf = max(conf, float(s.get("confidence") or 0.0))
        stale = stale or bool(s.get("stale"))
    context_load_ms = round((time.perf_counter() - started) * 1000.0, 2)
    if not used:
        return None
    high_conf = conf >= 0.7 and not missing
    if conf < 0.65 and missing:
        return None
    quality_score, quality_reasons = _quality_gate(
        message=message,
        used=used,
        missing=missing,
        stale=stale,
        conf=conf,
    )
    low_quality = quality_score < 0.62
    msg_l = (message or "").lower()
    lines = []
    for s in used:
        lines.append(f"### {s.get('snapshot_type')}\n- generated_at: `{s.get('generated_at')}`\n- summary: {s.get('summary_short')}")
    # Doc cleanup/status questions get structured repo_pulse details.
    if any(k in msg_l for k in ("documentation", "docs", "readme", "cleanup")):
        rp = next((s for s in used if s.get("snapshot_type") == "repo_pulse"), None)
        if isinstance(rp, dict):
            d = rp.get("data") or {}
            docs_need = d.get("docs_needing_updates") or []
            stale_repos = d.get("stale_repos") or []
            repos = d.get("repos") or []
            lines.append("### documentation_cleanup_status")
            lines.append(f"- docs_needing_updates: {docs_need[:8]}")
            lines.append(f"- stale_repos: {[r.get('repo') for r in stale_repos[:8] if isinstance(r, dict)]}")
            src_paths = [r.get("path") for r in repos[:8] if isinstance(r, dict) and r.get("path")]
            if src_paths:
                lines.append(f"- source_paths: {src_paths}")
    warning = ""
    if stale:
        warning = (
            "\n\n⚠️ Prepared context is stale. I can answer from cached state now, and you can refresh with "
            "`python scripts/build_prepared_context.py --snapshot all`."
        )
    if missing:
        warning += f"\n\nMissing prepared snapshots: {missing}. Falling back to retrieval/model is available if needed."
    if low_quality:
        missing_bits: list[str] = []
        if stale:
            missing_bits.append("snapshot freshness")
        if quality_reasons.get("evidence_items_count", 0) <= 1:
            missing_bits.append("evidence breadth")
        if quality_reasons.get("source_traceability", 1.0) < 0.7:
            missing_bits.append("source traceability")
        if missing:
            missing_bits.append(f"missing snapshots: {missing}")
        limited = [
            "_Prepared context is available but incomplete for a high-confidence full answer._",
            "",
            "### limited_summary",
            "\n".join(lines[:2]) if lines else "- no prepared snapshot lines available",
            "",
            f"- quality_score: `{quality_score}`",
            f"- missing_data: {missing_bits if missing_bits else ['none declared']}",
            "Use `python scripts/build_prepared_context.py --snapshot all` to refresh before relying on full status.",
        ]
        reply = "\n".join(limited) + warning
    else:
        reply = "\n\n".join(lines) + warning
    return {
        "reply": reply,
        "prepared_context_used": True,
        "snapshot_types_used": [s.get("snapshot_type") for s in used],
        "snapshot_generated_at": {s.get("snapshot_type"): s.get("generated_at") for s in used},
        "snapshot_stale": stale,
        "context_load_ms": context_load_ms,
        "avoided_retrieval": high_conf,
        "avoided_worker_call": True,
        "final_answer_source": "prepared_context" if high_conf else "prepared_context_plus_model",
        "confidence": conf,
        "prepared_quality_score": quality_score,
        "prepared_quality_reasons": quality_reasons,
        "prepared_quality_low": low_quality,
    }

