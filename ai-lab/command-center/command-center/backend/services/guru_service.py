from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.ai_lab import AI_LAB_ROOT


MODE_DEFAULTS = {
    "RR": {
        "label": "Response Refinement",
        "save_policy": "direct",
        "description": "Shapes future response style, citations, and evidence habits.",
        "system_prompt": "Use this thread to refine future response behavior. Normalize requests into structured response rules.",
    },
    "PR": {
        "label": "Proposal Refinement",
        "save_policy": "direct",
        "description": "Shapes proposal structure, planning format, and recommendation style.",
        "system_prompt": "Use this thread to refine future proposal behavior. Normalize requests into structured planning rules.",
    },
    "AL": {
        "label": "Action List",
        "save_policy": "confirm",
        "description": "Shapes how action lists are broken down, ordered, and presented.",
        "system_prompt": "Use this thread to draft changes to action-list behavior. Preview changes before saving.",
    },
    "TL": {
        "label": "Tool List",
        "save_policy": "confirm",
        "description": "Shapes how tools, capabilities, and safety notes are presented.",
        "system_prompt": "Use this thread to draft changes to tool-list behavior. Preview changes before saving.",
    },
    "ATL": {
        "label": "Auto Task List",
        "save_policy": "confirm",
        "description": "Shapes what can auto-run without approval by updating trust and allow rules.",
        "system_prompt": "Use this thread to propose auto-allow policy updates. Always preview before saving.",
    },
}

MEMORY_DIR = AI_LAB_ROOT / "memory"
POLICY_DIR = AI_LAB_ROOT / "policy"
LOG_DIR = AI_LAB_ROOT / "logs"
THREAD_DIR = LOG_DIR / "guru_threads"
AUDIT_DIR = LOG_DIR / "config_changes"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    THREAD_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _thread_path(mode: str) -> Path:
    return THREAD_DIR / f"{mode.upper()}.json"


def _default_thread(mode: str) -> dict[str, Any]:
    meta = MODE_DEFAULTS[mode]
    return {
        "mode": mode,
        "messages": [
            {
                "id": f"MSG-{uuid4().hex[:8]}",
                "role": "sys",
                "text": meta["system_prompt"],
                "timestamp": _now(),
            }
        ],
        "current_draft": None,
        "last_saved_summary": None,
        "last_updated_at": None,
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _read_text(path: Path, default: str) -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8")


def _load_allowlists() -> dict[str, list[str]]:
    path = POLICY_DIR / "allowlists.yaml"
    content = _read_text(path, "# Scripts or paths allowed without approval (within tier). One per line or YAML list.\nscripts: []\npaths: []\n")
    scripts: list[str] = []
    paths: list[str] = []
    current: str | None = None

    for raw in content.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("scripts:"):
            current = "scripts"
            if line.endswith("[]"):
                continue
        elif line.startswith("paths:"):
            current = "paths"
            if line.endswith("[]"):
                continue
        elif line.startswith("- ") and current:
            if current == "scripts":
                scripts.append(line[2:].strip())
            else:
                paths.append(line[2:].strip())

    return {"scripts": scripts, "paths": paths}


def _dump_allowlists(data: dict[str, list[str]]) -> str:
    lines = ["# Scripts or paths allowed without approval (within tier). One per line or YAML list."]
    for key in ("scripts", "paths"):
        values = sorted(dict.fromkeys(v for v in data.get(key, []) if v))
        if values:
            lines.append(f"{key}:")
            lines.extend([f"  - {value}" for value in values])
        else:
            lines.append(f"{key}: []")
    return "\n".join(lines) + "\n"


def _append_message(thread: dict[str, Any], role: str, text: str) -> None:
    thread["messages"].append(
        {
            "id": f"MSG-{uuid4().hex[:8]}",
            "role": role,
            "text": text,
            "timestamp": _now(),
        }
    )


def _mode_scope_from_message(message: str) -> str:
    lowered = message.lower()
    if "repo " in lowered or "for this repo" in lowered:
        return "repo"
    if "workflow" in lowered:
        return "workflow"
    if "tool " in lowered:
        return "tool"
    if "path " in lowered or "docs/" in lowered or "src/" in lowered:
        return "path_pattern"
    if "topic" in lowered or "code discussion" in lowered:
        return "topic"
    return "global"


def _normalize_guidance(message: str) -> list[str]:
    normalized = " ".join(message.replace("\n", " ").split())
    parts = [part.strip(" .") for part in normalized.split(" but ")]
    return [part[:160] for part in parts if part]


def _load_thread(mode: str) -> dict[str, Any]:
    _ensure_dirs()
    path = _thread_path(mode)
    if not path.exists():
        thread = _default_thread(mode)
        _write_json(path, thread)
        return thread
    return _load_json(path, _default_thread(mode))


def _save_thread(mode: str, thread: dict[str, Any]) -> None:
    _ensure_dirs()
    _write_json(_thread_path(mode), thread)


def _upsert_workflow_rule(mode: str, scope: str, behavior: dict[str, Any], summary: str) -> None:
    path = MEMORY_DIR / "workflow_rules.json"
    rules = _load_json(path, [])
    updated = False
    for rule in rules:
        if rule.get("mode") == mode and rule.get("scope") == scope:
            rule["behavior"] = behavior
            rule["summary"] = summary
            rule["updated_at"] = _now()
            updated = True
            break
    if not updated:
        rules.append(
            {
                "id": f"{mode.lower()}-{scope}",
                "mode": mode,
                "scope": scope,
                "behavior": behavior,
                "summary": summary,
                "updated_at": _now(),
            }
        )
    _write_json(path, rules)


def _merge_trust_rules(new_rules: list[dict[str, Any]]) -> None:
    path = MEMORY_DIR / "trust_rules.json"
    existing = _load_json(path, [])
    merged = []
    seen = set()
    for rule in existing + new_rules:
        key = (
            rule.get("scope"),
            rule.get("path_pattern"),
            rule.get("tool_name"),
            rule.get("task_class"),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(rule)
    _write_json(path, merged)


def _capture_files(paths: list[Path]) -> dict[str, str]:
    captured: dict[str, str] = {}
    for path in paths:
        rel = str(path.relative_to(AI_LAB_ROOT))
        default = "" if path.suffix == ".json" else ""
        captured[rel] = _read_text(path, default)
    return captured


def _write_files(contents: dict[str, str]) -> None:
    for rel, value in contents.items():
        path = AI_LAB_ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_text(path, value)


def _record_audit(mode: str, summary: str, raw_message: str, before_files: dict[str, str], after_files: dict[str, str], draft: dict[str, Any] | None = None) -> dict[str, Any]:
    record = {
        "id": f"AUD-{uuid4().hex[:10]}",
        "mode": mode,
        "summary": summary,
        "raw_user_instruction": raw_message,
        "draft": draft,
        "before_files": before_files,
        "after_files": after_files,
        "created_at": _now(),
        "reverted": False,
    }
    path = AUDIT_DIR / f"{record['created_at'].replace(':', '-').replace('.', '-')}_{mode}.json"
    _write_json(path, record)
    return record


def _latest_audit_path(mode: str) -> Path | None:
    files = sorted(AUDIT_DIR.glob(f"*_{mode}.json"), reverse=True)
    return files[0] if files else None


def _normalize_rr(message: str) -> dict[str, Any]:
    lowered = message.lower()
    behavior: dict[str, Any] = {}
    if "source" in lowered or "reference" in lowered or "cite" in lowered:
        behavior["include_source_references"] = True
    if "file" in lowered or "path" in lowered:
        behavior["mention_relevant_files"] = True
    if "concise" in lowered or "brief" in lowered:
        behavior["verbosity"] = "concise"
    elif "detailed" in lowered or "detail" in lowered:
        behavior["verbosity"] = "detailed"
    if "observation" in lowered or "recommendation" in lowered:
        behavior["separate_observations_from_recommendations"] = True
    guidance = _normalize_guidance(message)
    if guidance:
        behavior["guidance_points"] = guidance[:3]
    summary_bits = []
    if behavior.get("include_source_references"):
        summary_bits.append("include source references")
    if behavior.get("mention_relevant_files"):
        summary_bits.append("mention relevant files")
    if behavior.get("verbosity"):
        summary_bits.append(f"use {behavior['verbosity']} tone")
    if behavior.get("separate_observations_from_recommendations"):
        summary_bits.append("separate observations from recommendations")
    return {
        "mode": "RR",
        "scope": _mode_scope_from_message(message),
        "behavior": behavior,
        "summary": "RR updated to " + (", ".join(summary_bits) if summary_bits else "capture refined response guidance"),
    }


def _normalize_pr(message: str) -> dict[str, Any]:
    lowered = message.lower()
    behavior: dict[str, Any] = {
        "guidance_points": _normalize_guidance(message)[:3],
    }
    if "now" in lowered and "next" in lowered and "later" in lowered:
        behavior["proposal_structure"] = "now_next_later"
    if "risk" in lowered:
        behavior["include_risks"] = True
    if "dependenc" in lowered:
        behavior["include_dependencies"] = True
    return {
        "mode": "PR",
        "scope": _mode_scope_from_message(message),
        "behavior": behavior,
        "summary": "PR updated to refine proposal structure and planning guidance",
    }


def _normalize_al(message: str) -> dict[str, Any]:
    lowered = message.lower()
    behavior: dict[str, Any] = {
        "guidance_points": _normalize_guidance(message)[:3],
        "include_acceptance_criteria": "acceptance" in lowered or "criteria" in lowered,
        "order": "blockers_first" if "blocker" in lowered else "sequential",
    }
    if "backend" in lowered and "frontend" in lowered:
        behavior["group_by"] = "backend_frontend"
    return {
        "mode": "AL",
        "scope": _mode_scope_from_message(message),
        "behavior": behavior,
        "summary": "AL draft prepared for action-list behavior changes",
    }


def _normalize_tl(message: str) -> dict[str, Any]:
    lowered = message.lower()
    behavior: dict[str, Any] = {
        "guidance_points": _normalize_guidance(message)[:3],
        "show_approval_requirement": "approval" in lowered,
        "show_read_only_vs_mutating": "read" in lowered or "mutat" in lowered or "state" in lowered,
        "group_by": "rig" if "rig" in lowered or "worker" in lowered or "main" in lowered else "category",
    }
    return {
        "mode": "TL",
        "scope": _mode_scope_from_message(message),
        "behavior": behavior,
        "summary": "TL draft prepared for tool-list presentation changes",
    }


def _normalize_atl(message: str) -> dict[str, Any]:
    lowered = message.lower()
    rules: list[dict[str, Any]] = []
    if "health" in lowered:
        rules.append({"scope": "task_class", "task_class": "health_check", "approval_required": False})
    if ("repo" in lowered and "scan" in lowered) or "summaries" in lowered:
        rules.append({"scope": "task_class", "task_class": "repo_scan_to_summaries", "approval_required": False})
    if "registry" in lowered and ("lookup" in lowered or "read" in lowered):
        rules.append({"scope": "task_class", "task_class": "registry_read", "approval_required": False})
    if "semantic" in lowered or "retrieve" in lowered or "retrieval" in lowered:
        rules.append({"scope": "task_class", "task_class": "semantic_retrieval", "approval_required": False})
    if not rules:
        rules.append({"scope": "task_class", "task_class": "custom_safe_task", "approval_required": False})
    return {
        "mode": "ATL",
        "scope": _mode_scope_from_message(message),
        "rules": rules,
        "summary": "ATL draft prepared for auto-allow rule updates",
    }


def _normalize_message(mode: str, message: str) -> dict[str, Any]:
    normalizers = {
        "RR": _normalize_rr,
        "PR": _normalize_pr,
        "AL": _normalize_al,
        "TL": _normalize_tl,
        "ATL": _normalize_atl,
    }
    return normalizers[mode](message)


def _apply_direct(mode: str, draft: dict[str, Any], raw_message: str) -> tuple[str, dict[str, Any]]:
    touched = [MEMORY_DIR / "preferences.json", MEMORY_DIR / "workflow_rules.json"]
    before = _capture_files(touched)

    if mode == "RR":
        prefs_path = MEMORY_DIR / "preferences.json"
        prefs = _load_json(prefs_path, {})
        behavior = draft["behavior"]
        if behavior.get("include_source_references"):
            prefs["include_source_references_in_code_discussions"] = True
        if behavior.get("mention_relevant_files"):
            prefs["mention_relevant_files_when_relevant"] = True
        if behavior.get("verbosity"):
            prefs["default_response_verbosity"] = behavior["verbosity"]
        if behavior.get("separate_observations_from_recommendations"):
            prefs["separate_observations_from_recommendations"] = True
        _write_json(prefs_path, prefs)
        _upsert_workflow_rule(mode, draft["scope"], draft["behavior"], draft["summary"])
    elif mode == "PR":
        _upsert_workflow_rule(mode, draft["scope"], draft["behavior"], draft["summary"])

    after = _capture_files(touched)
    audit = _record_audit(mode, draft["summary"], raw_message, before, after, draft)
    return draft["summary"], audit


def _apply_confirm(mode: str, draft: dict[str, Any], raw_message: str) -> tuple[str, dict[str, Any]]:
    touched = [MEMORY_DIR / "workflow_rules.json", MEMORY_DIR / "trust_rules.json", POLICY_DIR / "allowlists.yaml"]
    before = _capture_files(touched)

    if mode in {"AL", "TL"}:
        _upsert_workflow_rule(mode, draft["scope"], draft["behavior"], draft["summary"])
    elif mode == "ATL":
        _merge_trust_rules(draft["rules"])
        allowlists = _load_allowlists()
        for rule in draft["rules"]:
            if rule.get("scope") == "tool" and rule.get("tool_name"):
                allowlists["scripts"].append(rule["tool_name"])
            if rule.get("scope") == "path_pattern" and rule.get("path_pattern"):
                allowlists["paths"].append(rule["path_pattern"])
        _write_text(POLICY_DIR / "allowlists.yaml", _dump_allowlists(allowlists))

    after = _capture_files(touched)
    audit = _record_audit(mode, draft["summary"], raw_message, before, after, draft)
    return draft["summary"], audit


def _mode_current_rules(mode: str) -> dict[str, Any]:
    prefs = _load_json(MEMORY_DIR / "preferences.json", {})
    workflow_rules = _load_json(MEMORY_DIR / "workflow_rules.json", [])
    trust_rules = _load_json(MEMORY_DIR / "trust_rules.json", [])
    allowlists = _load_allowlists()

    if mode == "RR":
        relevant_prefs = {
            key: value
            for key, value in prefs.items()
            if key in {
                "include_source_references_in_code_discussions",
                "mention_relevant_files_when_relevant",
                "default_response_verbosity",
                "separate_observations_from_recommendations",
            }
        }
        return {
            "preferences": relevant_prefs,
            "workflow_rules": [rule for rule in workflow_rules if rule.get("mode") == "RR"],
        }

    if mode in {"PR", "AL", "TL"}:
        return {
            "workflow_rules": [rule for rule in workflow_rules if rule.get("mode") == mode],
        }

    return {
        "trust_rules": [rule for rule in trust_rules if rule.get("task_class") or rule.get("tool_name") or rule.get("path_pattern")],
        "allowlists": allowlists,
    }


def snapshot() -> dict[str, Any]:
    return {
        "modes": {
            mode: get_mode(mode)
            for mode in MODE_DEFAULTS
        }
    }


def get_mode(mode: str) -> dict[str, Any]:
    mode = mode.upper()
    thread = _load_thread(mode)
    meta = MODE_DEFAULTS[mode]
    return {
        "mode": mode,
        "label": meta["label"],
        "description": meta["description"],
        "save_policy": meta["save_policy"],
        "messages": thread["messages"],
        "current_draft": thread.get("current_draft"),
        "last_saved_summary": thread.get("last_saved_summary"),
        "last_updated_at": thread.get("last_updated_at"),
        "current_rules": _mode_current_rules(mode),
    }


def submit_mode_message(mode: str, message: str) -> dict[str, Any]:
    mode = mode.upper()
    thread = _load_thread(mode)
    _append_message(thread, "user", message)
    draft = _normalize_message(mode, message)

    if MODE_DEFAULTS[mode]["save_policy"] == "direct":
        summary, audit = _apply_direct(mode, draft, message)
        thread["current_draft"] = None
        thread["last_saved_summary"] = summary
        thread["last_updated_at"] = _now()
        _append_message(thread, "assistant", summary)
        _save_thread(mode, thread)
        return {**get_mode(mode), "saved": True, "summary": summary, "audit_id": audit["id"]}

    thread["current_draft"] = {
        "draft": draft,
        "raw_message": message,
        "created_at": _now(),
    }
    _append_message(thread, "assistant", f"Draft ready. Review and confirm to save: {draft['summary']}")
    _save_thread(mode, thread)
    return {**get_mode(mode), "saved": False, "summary": draft["summary"]}


def confirm_mode(mode: str) -> dict[str, Any]:
    mode = mode.upper()
    thread = _load_thread(mode)
    current_draft = thread.get("current_draft")
    if not current_draft:
        raise ValueError(f"No pending draft for {mode}.")

    summary, audit = _apply_confirm(mode, current_draft["draft"], current_draft["raw_message"])
    thread["current_draft"] = None
    thread["last_saved_summary"] = summary
    thread["last_updated_at"] = _now()
    _append_message(thread, "assistant", f"Confirmed and saved. {summary}")
    _save_thread(mode, thread)
    return {**get_mode(mode), "saved": True, "summary": summary, "audit_id": audit["id"]}


def revert_last(mode: str) -> dict[str, Any]:
    mode = mode.upper()
    audit_path = _latest_audit_path(mode)
    if not audit_path:
        raise ValueError(f"No saved changes found for {mode}.")
    audit = _load_json(audit_path, {})
    if audit.get("reverted"):
        raise ValueError(f"Latest change for {mode} was already reverted.")
    _write_files(audit.get("before_files", {}))
    audit["reverted"] = True
    audit["reverted_at"] = _now()
    _write_json(audit_path, audit)

    thread = _load_thread(mode)
    thread["current_draft"] = None
    thread["last_saved_summary"] = f"Reverted last {mode} change."
    thread["last_updated_at"] = _now()
    _append_message(thread, "assistant", f"Reverted last {mode} change.")
    _save_thread(mode, thread)
    return {**get_mode(mode), "saved": True, "summary": f"Reverted last {mode} change.", "audit_id": audit.get("id")}
