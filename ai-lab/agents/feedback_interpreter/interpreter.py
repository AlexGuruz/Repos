"""
Feedback interpreter: classify user input (correction, approval, denial, revised approval, workflow preference)
and update memory (trust_rules, preferences, successful_workflows).
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

AI_LAB_ROOT = Path(__file__).resolve().parents[2]
MEMORY = AI_LAB_ROOT / "memory"


def _load_json(name: str) -> list | dict:
    p = MEMORY / name
    if not p.exists():
        return [] if "workflows" in name or "rules" in name else {}
    with open(p) as f:
        return json.load(f)


def _save_json(name: str, data: list | dict) -> None:
    with open(MEMORY / name, "w") as f:
        json.dump(data, f, indent=2)


def classify(text: str) -> str:
    """Classify feedback: correction, approval, denial, revised_approval, workflow_preference, other."""
    t = (text or "").strip().lower()
    if "don't" in t or "do not" in t or "use existing" in t or "exclude" in t:
        return "correction"
    if t.startswith("approve") or "approved" in t or "yes" in t and "approval" in t:
        return "approval"
    if t.startswith("deny") or "denied" in t or "no " in t or "reject" in t:
        return "denial"
    if "can edit" in t or "allow that script" in t:
        return "revised_approval"
    if "prefer" in t or "always" in t or "timezone" in t:
        return "workflow_preference"
    return "other"


def apply_feedback(text: str, context: dict | None = None) -> str:
    """
    Classify feedback and update memory. Return short description of what was updated.
    """
    kind = classify(text)
    context = context or {}
    if kind == "approval" and context.get("approval_id"):
        # Could resolve approval_queue here
        return f"Recorded approval for {context['approval_id']}."
    if kind == "denial" and context.get("approval_id"):
        return f"Recorded denial for {context['approval_id']}."
    if kind == "correction":
        prefs = _load_json("preferences.json")
        if isinstance(prefs, dict):
            prefs["reuse_existing_scripts_first"] = True
            _save_json("preferences.json", prefs)
        return "Updated preferences (reuse existing scripts first)."
    if kind == "workflow_preference":
        prefs = _load_json("preferences.json")
        if isinstance(prefs, dict):
            prefs["last_feedback"] = text[:200]
            _save_json("preferences.json", prefs)
        return "Stored workflow preference."
    if kind == "other":
        return "Feedback noted; no memory update."
    return f"Classified as {kind}; no automatic update."
