"""
Deterministic validation of README, runbook, and system map docs against repo_doc_policy.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from brain.repo_doc_policy import (
    ACTIONABLE_LINE_HINTS,
    PLACEHOLDER_SUBSTRINGS,
    README_OPTIONAL,
    README_REQUIRED,
    README_RULES,
    RUNBOOK_OPTIONAL,
    RUNBOOK_REQUIRED,
    RUNBOOK_RULES,
    SYSTEM_MAP_OPTIONAL,
    SYSTEM_MAP_REQUIRED,
    SYSTEM_MAP_RULES,
    SectionPolicy,
)


def _norm_heading(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _heading_matches(policy: SectionPolicy, heading: str) -> bool:
    h = _norm_heading(heading)
    return any(p in h for p in policy.heading_patterns)


def _first_h1_intro(text: str) -> str:
    """Body text after first # title until first ## (common README overview location)."""
    lines = text.splitlines()
    in_h1 = False
    buf: list[str] = []
    for line in lines:
        if line.startswith("# ") and not in_h1:
            in_h1 = True
            continue
        if in_h1:
            if line.startswith("##"):
                break
            buf.append(line)
    return "\n".join(buf).strip()


def _extract_sections(text: str) -> dict[str, str]:
    """
    Split markdown by top-level # or ## headings into section key = heading text, value = body until next same-or-higher level.
    """
    lines = text.splitlines()
    sections: dict[str, str] = {}
    current_title: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is not None:
            sections[current_title] = "\n".join(current_lines).strip()
        current_title = None
        current_lines = []

    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if level <= 2:
                flush()
                current_title = title
                current_lines = []
            else:
                if current_title is not None:
                    current_lines.append(line)
        else:
            if current_title is not None:
                current_lines.append(line)
            elif not sections:
                preamble = sections.get("__preamble__", "")
                sections["__preamble__"] = (preamble + "\n" + line).strip()
    flush()
    if "__preamble__" in sections and not sections["__preamble__"]:
        del sections["__preamble__"]
    return sections


def _section_for_policy(
    sections: dict[str, str], policy: SectionPolicy
) -> tuple[str | None, str]:
    for title, body in sections.items():
        if title.startswith("__"):
            continue
        if _heading_matches(policy, title):
            return title, body
    return None, ""


def _has_placeholder(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in PLACEHOLDER_SUBSTRINGS)


def _has_actionable(text: str) -> bool:
    for line in text.splitlines():
        s = line.strip().lower()
        if any(h in s for h in ACTIONABLE_LINE_HINTS):
            return True
    return False


def _min_body_chars() -> int:
    return 40


def _validate_doc_type(
    path: Path,
    doc_kind: str,
    required: tuple[SectionPolicy, ...],
    optional: tuple[SectionPolicy, ...],
    rules: dict[str, Any],
) -> dict[str, Any]:
    missing_sections: list[str] = []
    weak_sections: list[str] = []
    suggestions: list[str] = []

    if not path.is_file():
        return {
            "path": str(path),
            "doc_kind": doc_kind,
            "is_valid": False,
            "missing_sections": ["<file missing>"],
            "weak_sections": [],
            "suggestions": [f"Create or restore {path.name} at this path."],
            "confidence": 1.0,
        }

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return {
            "path": str(path),
            "doc_kind": doc_kind,
            "is_valid": False,
            "missing_sections": [p.key for p in required],
            "weak_sections": ["<empty file>"],
            "suggestions": ["Add content structured per policy required sections."],
            "confidence": 1.0,
        }

    sections = _extract_sections(text)

    for pol in required:
        title, body = _section_for_policy(sections, pol)
        if title is None and pol.key == "overview" and doc_kind == "readme":
            intro = _first_h1_intro(text)
            if len(intro) >= _min_body_chars():
                title, body = "<h1 intro>", intro
        if title is None:
            missing_sections.append(pol.key)
            suggestions.append(
                f"Add a section for '{pol.key}' (e.g. heading matching: {', '.join(pol.heading_patterns[:3])})."
            )
        else:
            if len(body) < _min_body_chars():
                weak_sections.append(pol.key)
                suggestions.append(
                    f"Expand '{pol.key}' (heading '{title}'): add concrete steps, commands, or links (min ~{_min_body_chars()} chars of substance)."
                )
            if rules.get("forbid_placeholder_headings") and _has_placeholder(body):
                weak_sections.append(f"{pol.key}:placeholder")
                suggestions.append(f"Remove placeholder language in '{pol.key}' section.")

    if rules.get("require_actionable_step") and not _has_actionable(text):
        weak_sections.append("no_actionable_command")
        suggestions.append(
            "Include at least one actionable command or step (e.g. fenced code block, npm/pip/python/docker invocation)."
        )

    optional_hits = [p.key for p in optional if _section_for_policy(sections, p)[0] is not None]
    if optional_hits:
        suggestions.append(f"Optional sections present: {', '.join(optional_hits)}.")

    checks = len(required) + 3
    passed = checks - len(missing_sections) - min(len(weak_sections), len(required) + 2)
    confidence = max(0.35, min(1.0, passed / max(checks, 1)))

    is_valid = not missing_sections and not weak_sections

    return {
        "path": str(path),
        "doc_kind": doc_kind,
        "is_valid": is_valid,
        "missing_sections": missing_sections,
        "weak_sections": weak_sections,
        "suggestions": suggestions[:25],
        "confidence": round(confidence, 2),
    }


def validate_readme(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return _validate_doc_type(p, "readme", README_REQUIRED, README_OPTIONAL, README_RULES)


def validate_runbook(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return _validate_doc_type(p, "runbook", RUNBOOK_REQUIRED, RUNBOOK_OPTIONAL, RUNBOOK_RULES)


def validate_system_map(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return _validate_doc_type(
        p, "system_map", SYSTEM_MAP_REQUIRED, SYSTEM_MAP_OPTIONAL, SYSTEM_MAP_RULES
    )
