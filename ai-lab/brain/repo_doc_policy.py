"""
Repo documentation policy definitions (Phase 7).

Deterministic rules only — no LLM. Used by repo_doc_validation and repo_docs_maintainer.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SectionPolicy:
    """A required or optional documentation section identified by heading patterns."""

    key: str
    heading_patterns: tuple[str, ...]


README_REQUIRED: tuple[SectionPolicy, ...] = (
    SectionPolicy("overview", ("overview", "introduction", "about", "purpose")),
    SectionPolicy("setup", ("setup", "installation", "getting started", "quick start")),
    SectionPolicy("configuration", ("configuration", "environment", "env vars", "variables", ".env")),
    SectionPolicy("usage", ("usage", "running", "how to run", "entrypoint", "commands")),
    SectionPolicy("architecture", ("architecture", "system overview", "design", "how it works")),
    SectionPolicy("verification", ("verification", "testing", "how to confirm", "validate", "check that")),
)

README_OPTIONAL: tuple[SectionPolicy, ...] = (
    SectionPolicy("troubleshooting", ("troubleshooting", "faq", "common issues")),
    SectionPolicy("roadmap", ("roadmap", "future work", "planned")),
    SectionPolicy("dependencies", ("dependencies", "requirements", "prerequisites")),
)

README_RULES: dict[str, object] = {
    "required_sections_non_empty": True,
    "forbid_placeholder_headings": True,
    "require_actionable_step": True,
}

PLACEHOLDER_SUBSTRINGS: tuple[str, ...] = (
    "todo",
    "tbd",
    "fixme",
    "lorem ipsum",
    "xxx",
    "coming soon",
    "[placeholder]",
    "fill in later",
)

ACTIONABLE_LINE_HINTS: tuple[str, ...] = (
    "```",
    "npm ",
    "pnpm ",
    "yarn ",
    "pip ",
    "python ",
    "uv ",
    "cargo ",
    "make ",
    "./",
    "docker ",
    "powershell",
    "pwsh ",
)


RUNBOOK_REQUIRED: tuple[SectionPolicy, ...] = (
    SectionPolicy("purpose", ("purpose", "objective", "goal", "why")),
    SectionPolicy("steps", ("steps", "procedure", "instructions", "how to")),
    SectionPolicy("expected_result", ("expected", "success", "outcome", "verify")),
    SectionPolicy("failure_handling", ("failure", "rollback", "if something goes wrong", "troubleshoot")),
)

RUNBOOK_OPTIONAL: tuple[SectionPolicy, ...] = (
    SectionPolicy("prerequisites", ("prerequisites", "requirements", "before you start")),
)

RUNBOOK_RULES: dict[str, object] = {
    "required_sections_non_empty": True,
    "forbid_placeholder_headings": True,
    "require_actionable_step": True,
}


SYSTEM_MAP_REQUIRED: tuple[SectionPolicy, ...] = (
    SectionPolicy("components", ("components", "services", "modules", "parts")),
    SectionPolicy("data_flow", ("data flow", "flow", "relationships", "diagram")),
    SectionPolicy("integration", ("integration", "interfaces", "external", "apis")),
)

SYSTEM_MAP_OPTIONAL: tuple[SectionPolicy, ...] = (
    SectionPolicy("ownership", ("ownership", "contacts", "on-call")),
)

SYSTEM_MAP_RULES: dict[str, object] = {
    "required_sections_non_empty": True,
    "forbid_placeholder_headings": True,
}
