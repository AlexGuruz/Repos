"""
Vendor lookup v2 — resolve unknown merchants after deterministic cleaning fails.
Never writes to sheet columns C/D; proposes candidates only.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from brain.bank_vendor_cleaner.engine import (
    FIXED_EVENT_LABELS,
    build_alias_lookup,
    format_location,
    get_label_with_source,
    is_fixed_event_label,
    normalize_text,
)
from brain.bank_vendor_cleaner.loader import (
    load_alias_map,
    load_cleaning_rules,
    load_vendor_lookup_cache,
    load_vendor_lookup_providers,
    load_vendor_lookup_rules,
    resolve_config_path,
)
from brain.bank_vendor_cleaner.paths import default_vendor_lookup_cache_path, reports_dir

Confidence = str  # low | medium | high
Decision = str  # cache_candidate | manual_review | reject


@dataclass
class LookupEvidence:
    source: str
    match_reason: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "match_reason": self.match_reason}


@dataclass
class LookupResult:
    raw_input: str
    candidate_label: str
    candidate_city: str
    candidate_state: str
    confidence: Confidence
    evidence: list[LookupEvidence] = field(default_factory=list)
    decision: Decision = "manual_review"
    deterministic_label: str = ""
    deterministic_location: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "candidate_label": self.candidate_label,
            "candidate_city": self.candidate_city,
            "candidate_state": self.candidate_state,
            "confidence": self.confidence,
            "evidence": [e.to_dict() for e in self.evidence],
            "decision": self.decision,
            "deterministic_label": self.deterministic_label,
            "deterministic_location": self.deterministic_location,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_location(location: str) -> tuple[str, str]:
    loc = normalize_text(location)
    if not loc:
        return "", ""
    if "," in loc:
        city, state = loc.split(",", 1)
        return city.strip(), state.strip()
    if len(loc) == 2 and loc.isalpha():
        return "", loc.upper()
    return loc, ""


def _normalize_lookup_query(raw: str) -> str:
    text = normalize_text(raw)
    text = re.sub(r"(?i)pos purchase|recur payment|online payment|internet payment", "", text)
    text = re.sub(r"(?i)seq#\s*\S+", "", text)
    text = re.sub(r"\b\d{3}[-.]?\d{3,}\b", "", text)
    text = re.sub(r"\b\d{2}/\d{2}(?:/\d{2,4})?\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120]


def should_trigger_lookup(
    raw: str,
    deterministic_label: str,
    label_source: str,
    *,
    rules: dict[str, Any] | None = None,
    inside_boundary: bool = True,
    is_formula: bool = False,
) -> bool:
    rules = rules or load_vendor_lookup_rules()
    if not rules.get("enabled", True):
        return False
    if is_formula:
        return False
    if not inside_boundary:
        return False
    raw_norm = normalize_text(raw)
    if not raw_norm:
        return False
    if label_source in {"alias", "rule", "blank"}:
        return False
    if is_fixed_event_label(deterministic_label):
        return False
    if rules.get("lookup_only_on_unknown", True) and label_source != "fallback":
        return False
    return True


def _confidence_rank(level: Confidence) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get(level, 0)


def _meets_minimum(confidence: Confidence, minimum: Confidence) -> bool:
    return _confidence_rank(confidence) >= _confidence_rank(minimum)


def _match_cache_entry(raw: str, pattern: str) -> bool:
    p = normalize_text(pattern).lower()
    r = normalize_text(raw).lower()
    if not p:
        return False
    if p == r:
        return True
    if p in r or r in p:
        return True
    return False


def _provider_local_cache(
    raw: str,
    cache: dict[str, Any],
) -> LookupResult | None:
    for section, approved_default in (("entries", True), ("pending", False)):
        for item in cache.get(section) or []:
            if not isinstance(item, dict):
                continue
            pattern = str(item.get("raw_pattern") or "")
            if not _match_cache_entry(raw, pattern):
                continue
            approved = bool(item.get("approved", approved_default))
            label = str(
                item.get("canonical_label")
                or item.get("candidate_label")
                or ""
            )
            city = str(item.get("city") or item.get("candidate_city") or "")
            state = str(item.get("state") or item.get("candidate_state") or "")
            conf = str(item.get("confidence") or "medium").lower()
            if conf not in {"low", "medium", "high"}:
                conf = "medium"
            decision: Decision = "cache_candidate" if approved else "manual_review"
            return LookupResult(
                raw_input=raw,
                candidate_label=label,
                candidate_city=city,
                candidate_state=state,
                confidence=conf,  # type: ignore[arg-type]
                evidence=[
                    LookupEvidence(
                        source="local_cache",
                        match_reason=f"matched {section} pattern: {pattern[:80]}",
                    )
                ],
                decision=decision,
            )
    return None


def _provider_mcp_web_search(
    raw: str,
    *,
    city_hint: str = "",
    state_hint: str = "",
    providers_cfg: dict[str, Any],
    timeout_sec: float = 10.0,
    max_results: int = 5,
    search_fn: Callable[..., list[dict[str, Any]]] | None = None,
) -> LookupResult | None:
    cfg = (providers_cfg.get("providers") or {}).get("mcp_web_search") or {}
    if not cfg.get("enabled", True):
        return None

    query = _normalize_lookup_query(raw)
    if city_hint or state_hint:
        query = f"{query} {city_hint} {state_hint}".strip()

    if search_fn is None:
        from brain.web_tool import web_search

        search_fn = web_search

    results = search_fn(query, max_results=max_results, timeout_sec=timeout_sec)
    if not results:
        return None

    top = results[0]
    title = str(top.get("title") or "").strip()
    snippet = str(top.get("snippet") or "").strip()
    name = title.split(" - ")[0].split(" | ")[0].strip() if title else ""
    if not name and snippet:
        name = snippet.split(".")[0][:64].strip()

    if not name:
        return None

    confidence: Confidence = "medium" if len(results) >= 2 else "low"
    return LookupResult(
        raw_input=raw,
        candidate_label=name[:64],
        candidate_city=city_hint,
        candidate_state=state_hint,
        confidence=confidence,
        evidence=[
            LookupEvidence(
                source=str(cfg.get("tool_name") or "mcp_web_search"),
                match_reason=f"top result: {title[:100]}",
            )
        ],
        decision="manual_review",
    )


def lookup_vendor(
    raw_input: str,
    *,
    deterministic_label: str = "",
    deterministic_location: str = "",
    city_hint: str = "",
    state_hint: str = "",
    label_source: str | None = None,
    inside_boundary: bool = True,
    is_formula: bool = False,
    rules: dict[str, Any] | None = None,
    providers_cfg: dict[str, Any] | None = None,
    cache: dict[str, Any] | None = None,
    search_fn: Callable[..., list[dict[str, Any]]] | None = None,
    write_pending: bool = True,
) -> LookupResult:
    """Run vendor lookup for one raw transaction string."""
    rules = rules or load_vendor_lookup_rules()
    providers_cfg = providers_cfg or load_vendor_lookup_providers()
    cache = cache if cache is not None else load_vendor_lookup_cache()

    alias_map = load_alias_map()
    cleaning_rules = load_cleaning_rules()
    alias_by_raw, _ = build_alias_lookup(alias_map)

    if not deterministic_label and label_source is None:
        deterministic_label, label_source = get_label_with_source(
            raw_input, alias_by_raw, cleaning_rules=cleaning_rules
        )
    label_source = label_source or "fallback"

    if city_hint or state_hint:
        pass
    elif deterministic_location:
        city_hint, state_hint = _parse_location(deterministic_location)

    reject = LookupResult(
        raw_input=raw_input,
        candidate_label="",
        candidate_city="",
        candidate_state="",
        confidence="low",
        evidence=[],
        decision="reject",
        deterministic_label=deterministic_label,
        deterministic_location=deterministic_location,
    )

    if not should_trigger_lookup(
        raw_input,
        deterministic_label,
        label_source,
        rules=rules,
        inside_boundary=inside_boundary,
        is_formula=is_formula,
    ):
        reject.evidence = [
            LookupEvidence(source="rules", match_reason="lookup not triggered for this row")
        ]
        return reject

    provider_order = rules.get("providers") or [
        "local_cache",
        "mcp_web_search",
        "manual_review",
    ]
    timeout = float(
        (providers_cfg.get("providers") or {})
        .get("mcp_web_search", {})
        .get("timeout_seconds", 10)
    )
    max_results = int(
        (providers_cfg.get("providers") or {})
        .get("mcp_web_search", {})
        .get("max_results", 5)
    )

    result: LookupResult | None = None
    for name in provider_order:
        if name == "local_cache":
            result = _provider_local_cache(raw_input, cache)
        elif name == "mcp_web_search":
            result = _provider_mcp_web_search(
                raw_input,
                city_hint=city_hint,
                state_hint=state_hint,
                providers_cfg=providers_cfg,
                timeout_sec=timeout,
                max_results=max_results,
                search_fn=search_fn,
            )
        elif name == "manual_review":
            result = None
        if result:
            break

    if result is None:
        result = LookupResult(
            raw_input=raw_input,
            candidate_label=deterministic_label,
            candidate_city=city_hint,
            candidate_state=state_hint,
            confidence="low",
            evidence=[
                LookupEvidence(
                    source="manual_review",
                    match_reason="no provider match; queue for human review",
                )
            ],
            decision="manual_review",
        )

    result.deterministic_label = deterministic_label
    result.deterministic_location = deterministic_location

    minimum = str(rules.get("minimum_confidence_for_pending_cache") or "medium").lower()
    if not _meets_minimum(result.confidence, minimum):  # type: ignore[arg-type]
        result.decision = "manual_review"

    if rules.get("require_human_approval_for_new_aliases", True):
        if result.decision == "cache_candidate":
            result.decision = "manual_review"

    if write_pending and result.decision in {"manual_review", "cache_candidate"}:
        _append_pending_cache(raw_input, result, cache, rules)

    return result


def _append_pending_cache(
    raw: str,
    result: LookupResult,
    cache: dict[str, Any],
    rules: dict[str, Any],
) -> None:
    if rules.get("allow_auto_promote_to_alias_map", False):
        return
    pending = cache.setdefault("pending", [])
    if not isinstance(pending, list):
        pending = []
        cache["pending"] = pending
    pattern = normalize_text(raw).lower()
    for item in pending:
        if isinstance(item, dict) and str(item.get("raw_pattern", "")).lower() == pattern:
            return
    pending.append(
        {
            "raw_pattern": pattern,
            "candidate_label": result.candidate_label,
            "candidate_city": result.candidate_city,
            "candidate_state": result.candidate_state,
            "confidence": result.confidence,
            "source": result.evidence[0].source if result.evidence else "vendor_lookup",
            "approved": False,
            "last_reviewed_at": _now_iso()[:10],
        }
    )
    import os

    cache_path = resolve_config_path(
        os.environ.get("VENDOR_LOOKUP_CACHE_PATH")
    ) or default_vendor_lookup_cache_path()
    if cache_path:
        _save_cache_yaml(cache_path, cache)

    queue_path = reports_dir() / "vendor_lookup_review_queue.json"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue: list[dict[str, Any]] = []
    if queue_path.is_file():
        try:
            queue = json.loads(queue_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            queue = []
    if not isinstance(queue, list):
        queue = []
    queue.append({**result.to_dict(), "queued_at": _now_iso()})
    queue_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")


def _save_cache_yaml(path: Path, data: dict[str, Any]) -> None:
    try:
        import yaml
    except ImportError:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def promote_approved_cache_entries(
    *,
    cache_path: Path | None = None,
    alias_map_path: Path | None = None,
) -> list[str]:
    """
    Copy approved cache entries into memory_alias_map.yaml.
    Returns list of promoted raw patterns. Does not write sheets.
    """
    from brain.bank_vendor_cleaner.loader import load_yaml
    from brain.bank_vendor_cleaner.paths import default_alias_map_path

    cache = load_vendor_lookup_cache(cache_path)
    alias_path = alias_map_path or default_alias_map_path()
    alias_map = load_yaml(alias_path)
    aliases = alias_map.setdefault("aliases", [])
    promoted: list[str] = []

    for item in cache.get("entries") or []:
        if not isinstance(item, dict) or not item.get("approved"):
            continue
        pattern = str(item.get("raw_pattern") or "")
        if not pattern:
            continue
        entry = {
            "id": f"cache_{len(aliases) + 1:03d}",
            "raw_inputs": [pattern],
            "canonical_label": str(item.get("canonical_label") or ""),
            "city": str(item.get("city") or ""),
            "state": str(item.get("state") or ""),
            "notes": "promoted from vendor_lookup_cache",
            "source": "vendor_lookup_cache",
            "confidence": str(item.get("confidence") or "high"),
        }
        aliases.append(entry)
        promoted.append(pattern)

    if promoted:
        try:
            import yaml

            alias_path.write_text(
                yaml.dump(alias_map, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
        except ImportError:
            pass
    return promoted
