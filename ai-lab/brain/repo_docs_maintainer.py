"""
Repo Documentation Maintainer (Phase 6–7).

Read-only analysis + proposal drafting for documentation upkeep.
No direct file modifications are performed in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from brain.orchestrator.approval_gate import requires_approval
from brain.prepared_context.loader import load_snapshot_fresh
from brain.repo_doc_policy import README_REQUIRED
from brain.repo_doc_validation import validate_readme, validate_runbook, validate_system_map


@dataclass
class DocsFinding:
    repo: str
    doc_file: str
    issue: str
    recommended_update: str
    risk_level: str
    approval_required: bool
    suggested_verification: str
    source_path: str
    stale: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "doc_file": self.doc_file,
            "issue": self.issue,
            "recommended_update": self.recommended_update,
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "suggested_verification": self.suggested_verification,
            "source_path": self.source_path,
            "stale": self.stale,
        }


def _risk_for_repo_row(row: dict[str, Any]) -> str:
    if not row.get("readme_present"):
        return "high"
    if not row.get("readme_fresh"):
        return "medium"
    if row.get("stale"):
        return "medium"
    return "low"


def _docs_issue_for_repo_row(row: dict[str, Any]) -> str | None:
    if not row.get("readme_present"):
        return "README missing"
    if not row.get("readme_fresh"):
        return "README stale"
    todo = int(row.get("todo_fixme_count") or 0)
    if todo >= 20:
        return "High TODO/FIXME density; docs likely lagging implementation"
    if row.get("stale"):
        return "Repository appears stale; docs may be outdated"
    return None


def _readme_file_path(row: dict[str, Any]) -> Path | None:
    repo_path = str(row.get("path") or "").strip()
    if not repo_path:
        return None
    return Path(repo_path) / "README.md"


def _policy_issue_summary(vr: dict[str, Any]) -> str | None:
    if vr.get("is_valid"):
        return None
    parts: list[str] = []
    if vr.get("missing_sections"):
        parts.append("missing: " + ", ".join(vr["missing_sections"]))
    if vr.get("weak_sections"):
        parts.append("weak: " + ", ".join(vr["weak_sections"]))
    return "README policy gaps (" + "; ".join(parts) + ")" if parts else "README policy validation failed"


def _build_finding(row: dict[str, Any], vr: dict[str, Any] | None = None) -> DocsFinding | None:
    issue = _docs_issue_for_repo_row(row)
    policy_issue = _policy_issue_summary(vr) if vr else None
    if policy_issue:
        issue = f"{issue}; {policy_issue}" if issue else policy_issue
    if not issue:
        return None
    repo = str(row.get("repo") or "unknown")
    repo_path = str(row.get("path") or "")
    rp = _readme_file_path(row) if row.get("path") else None
    doc_file = str(rp) if rp else f"{repo_path}/README.md" if repo_path else f"{repo}/README.md"
    risk = _risk_for_repo_row(row)
    if vr and not vr.get("is_valid"):
        risk = "high" if risk == "high" else "high" if vr.get("missing_sections") else "medium"
    rec_parts: list[str] = []
    if "README missing" in (issue or ""):
        rec_parts.append("Create README with purpose, setup, run commands, and ownership.")
    elif "README stale" in (issue or "") or "stale" in (issue or "").lower():
        rec_parts.append("Refresh README sections: current status, setup/run steps, and known caveats.")
    if "TODO/FIXME density" in (issue or ""):
        rec_parts.append("Add a short maintenance note linking TODO/FIXME clusters to roadmap/owner.")
    if vr and not vr.get("is_valid"):
        rec_parts.extend(vr.get("suggestions") or [])
    rec = " ".join(rec_parts) if rec_parts else "Align README with repo documentation policy."
    return DocsFinding(
        repo=repo,
        doc_file=doc_file,
        issue=issue,
        recommended_update=rec,
        risk_level=risk,
        approval_required=requires_approval("write_docs_update", "write_docs_update"),
        suggested_verification="Re-run repo_pulse and confirm readme_fresh=true or policy validation passes.",
        source_path=repo_path,
        stale=bool(row.get("stale")),
    )


def _finding_dict_with_validation(f: DocsFinding, vr: dict[str, Any] | None) -> dict[str, Any]:
    d = f.to_dict()
    if vr is not None:
        d["readme_validation"] = vr
    return d


def _discover_policy_docs(repo_root: Path) -> dict[str, list[str]]:
    """Lightweight discovery of runbooks and system maps (bounded, no repo-wide ** glob)."""
    out: dict[str, list[str]] = {"runbooks": [], "system_maps": []}
    if not repo_root.is_dir():
        return out

    def _scan_dir(d: Path, kind: str, max_n: int) -> None:
        if not d.is_dir():
            return
        key = "runbooks" if kind == "runbook" else "system_maps"
        try:
            names = sorted(d.iterdir())
        except OSError:
            return
        for p in names:
            if len(out[key]) >= max_n:
                return
            if not p.is_file():
                continue
            low = p.name.lower()
            if kind == "runbook" and "runbook" in low and low.endswith(".md"):
                out[key].append(str(p))
            elif kind == "map" and (
                "system_map" in low or "system-map" in low or low.endswith("architecture.md")
            ):
                out[key].append(str(p))

    docs = repo_root / "docs"
    _scan_dir(docs, "runbook", 3)
    _scan_dir(docs, "map", 2)
    _scan_dir(repo_root / "runbooks", "runbook", 3)
    _scan_dir(repo_root / "docs" / "runbooks", "runbook", 3)
    return out


def _validate_aux_docs(repo_root: Path) -> dict[str, Any]:
    rb_results: list[dict[str, Any]] = []
    sm_results: list[dict[str, Any]] = []
    disc = _discover_policy_docs(repo_root)
    for rb in disc["runbooks"][:3]:
        rb_results.append(validate_runbook(rb))
    for sm in disc["system_maps"][:2]:
        sm_results.append(validate_system_map(sm))
    return {"runbooks": rb_results, "system_maps": sm_results}


def _proposed_sections_for_readme(vr: dict[str, Any]) -> list[dict[str, Any]]:
    missing = [m for m in (vr.get("missing_sections") or []) if m not in ("<file missing>", "<empty file>")]
    weak = list(vr.get("weak_sections") or [])
    key_to_policy = {p.key: p for p in README_REQUIRED}
    proposed: list[dict[str, Any]] = []
    seen: set[str] = set()

    if "no_actionable_command" in weak:
        proposed.append(
            {
                "name": "Usage / commands",
                "policy_key": "usage",
                "outline": [
                    "Copy-paste commands to install and run locally.",
                    "Fenced code blocks for shell and config snippets.",
                ],
                "example_text": "```bash\nnpm install\nnpm test\n```",
                "reasoning": "README_RULES.require_actionable_step — reviewers need executable verification.",
            }
        )
        seen.add("usage")

    def _append_for_key(key: str) -> None:
        if key in seen:
            return
        pol = key_to_policy.get(key)
        if not pol:
            return
        seen.add(key)
        outline = [
            f"Heading matching: {', '.join(pol.heading_patterns[:4])}.",
            "2–4 short paragraphs or bullet lists; link to deeper docs if needed.",
        ]
        example_text = ""
        if pol.key == "verification":
            example_text = "- Run `pytest -q` and expect all green.\n- Smoke: start service and hit `/health`."
        proposed.append(
            {
                "name": pol.key.title(),
                "policy_key": pol.key,
                "outline": outline,
                "example_text": example_text,
                "reasoning": f"Required by README_POLICY for section '{pol.key}'.",
            }
        )

    for key in missing:
        _append_for_key(key)
    for w in weak:
        base = w.split(":", 1)[0] if ":" in w else w
        if base == "no_actionable_command":
            continue
        if base in key_to_policy:
            _append_for_key(base)
    return proposed


def analyze_repo_docs_status(
    *,
    message: str = "",
    target_repo: str | None = None,
    repo_pulse_snapshot: dict[str, Any] | None = None,
    system_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze repo documentation freshness from prepared context snapshots."""
    rp = repo_pulse_snapshot or load_snapshot_fresh("repo_pulse")
    ss = system_snapshot or load_snapshot_fresh("system_snapshot")

    missing_data: list[str] = []
    if not isinstance(rp, dict):
        missing_data.append("missing_repo_pulse_snapshot")
        return {
            "ok": False,
            "limited": True,
            "message": "repo_pulse snapshot unavailable",
            "missing_data": missing_data,
            "findings": [],
            "source_paths": [],
            "generated_at": None,
            "stale": True,
            "confidence": 0.0,
            "readme_validations": [],
            "aux_doc_validation": {},
        }

    data = rp.get("data") if isinstance(rp.get("data"), dict) else {}
    repos = list(data.get("repos") or [])
    if target_repo:
        t = target_repo.strip().lower()
        repos = [r for r in repos if str(r.get("repo") or "").lower() == t]
        if not repos:
            missing_data.append(f"target_repo_not_in_snapshot:{target_repo}")

    readme_validations: list[dict[str, Any]] = []
    aux_by_repo: dict[str, Any] = {}
    enriched_findings: list[dict[str, Any]] = []

    for r in repos:
        if not isinstance(r, dict):
            continue
        vr: dict[str, Any] | None = None
        rpth = _readme_file_path(r)
        if rpth is not None and bool(r.get("readme_present", True)):
            vr = validate_readme(rpth)
            entry = {"repo": str(r.get("repo") or ""), "path": str(rpth), **vr}
            readme_validations.append(entry)
        elif rpth is not None:
            readme_validations.append(
                {
                    "repo": str(r.get("repo") or ""),
                    "path": str(rpth),
                    "skipped": True,
                    "reason": "readme_absent_in_snapshot",
                }
            )
        repo_root = Path(str(r.get("path") or ""))
        if repo_root.is_dir():
            aux = _validate_aux_docs(repo_root)
            if aux["runbooks"] or aux["system_maps"]:
                aux_by_repo[str(r.get("repo") or "")] = aux

        pulse_finding = _build_finding(r, vr)
        if pulse_finding:
            enriched_findings.append(_finding_dict_with_validation(pulse_finding, vr))

    enriched_findings.sort(
        key=lambda x: (
            0 if x.get("risk_level") == "high" else 1 if x.get("risk_level") == "medium" else 2,
            -len((x.get("readme_validation") or {}).get("missing_sections") or []),
            x.get("repo") or "",
        ),
    )
    source_paths = [f.get("source_path") for f in enriched_findings if f.get("source_path")]

    return {
        "ok": True,
        "limited": bool(missing_data),
        "message": "repo documentation status from prepared context",
        "missing_data": missing_data,
        "findings": enriched_findings,
        "source_paths": sorted(set(source_paths)),
        "generated_at": rp.get("generated_at"),
        "stale": bool(rp.get("stale")),
        "confidence": float(rp.get("confidence") or 0.0),
        "system_generated_at": (ss or {}).get("generated_at") if isinstance(ss, dict) else None,
        "system_stale": bool((ss or {}).get("stale")) if isinstance(ss, dict) else None,
        "readme_validations": readme_validations,
        "aux_doc_validation": aux_by_repo,
    }


def _plan_priority_score(item: dict[str, Any]) -> int:
    vr = item.get("readme_validation") or {}
    score = 10 * len(vr.get("missing_sections") or [])
    score += 5 * len(vr.get("weak_sections") or [])
    if not vr.get("is_valid", True):
        score += 3
    if item.get("risk_level") == "high":
        score += 4
    elif item.get("risk_level") == "medium":
        score += 2
    return score


def build_docs_cleanup_plan(
    *,
    message: str = "",
    target_repo: str | None = None,
    max_items: int = 10,
) -> dict[str, Any]:
    """Build prioritized documentation cleanup plan from repo_pulse status + policy validation."""
    status = analyze_repo_docs_status(message=message, target_repo=target_repo)
    findings = list(status.get("findings") or [])
    if not findings:
        return {
            "ok": bool(status.get("ok")),
            "limited": True,
            "missing_data": list(status.get("missing_data") or []),
            "plan_items": [],
            "generated_from": "repo_pulse+policy",
            "notes": "No actionable documentation findings in current snapshot.",
            "readme_validations": status.get("readme_validations") or [],
            "aux_doc_validation": status.get("aux_doc_validation") or {},
        }
    plan_items: list[dict[str, Any]] = []
    for f in findings:
        vr = f.get("readme_validation")
        plan_items.append(
            {
                "repo": f["repo"],
                "doc_file": f["doc_file"],
                "issue_found": f["issue"],
                "recommended_update": f["recommended_update"],
                "risk_level": f["risk_level"],
                "approval_required": True,
                "suggested_verification": f["suggested_verification"],
                "readme_validation": vr,
                "priority_score": _plan_priority_score({**f, "readme_validation": vr}),
            }
        )
    plan_items.sort(key=lambda x: (-x.get("priority_score", 0), x.get("repo") or ""))
    plan_items = plan_items[:max_items]

    return {
        "ok": True,
        "limited": bool(status.get("limited")),
        "missing_data": list(status.get("missing_data") or []),
        "plan_items": plan_items,
        "generated_at": status.get("generated_at"),
        "stale": status.get("stale"),
        "confidence": status.get("confidence"),
        "source_paths": status.get("source_paths") or [],
        "generated_from": "repo_pulse+policy",
        "readme_validations": status.get("readme_validations") or [],
        "aux_doc_validation": status.get("aux_doc_validation") or {},
    }


def create_docs_update_proposal(
    *,
    message: str = "",
    target_repo: str | None = None,
    target_file: str | None = None,
) -> dict[str, Any]:
    """Create approval-gated docs update proposal from cleanup plan; no writes performed."""
    plan = build_docs_cleanup_plan(message=message, target_repo=target_repo, max_items=10)
    items = list(plan.get("plan_items") or [])
    if target_file:
        tf = target_file.strip().lower()
        items = [
            i
            for i in items
            if str(i.get("doc_file") or "").lower().endswith(tf)
            or str(i.get("doc_file") or "").lower() == tf
        ]
    top = items[0] if items else None
    approval_required = True
    action_type = "write_docs_update"
    classification = "modifies-files-or-state"
    vr = (top or {}).get("readme_validation") if top else None
    issues_list: list[str] = []
    if top:
        issues_list.append(str(top.get("issue_found") or ""))
    if isinstance(vr, dict):
        issues_list.extend([f"missing section: {m}" for m in (vr.get("missing_sections") or [])])
        issues_list.extend([f"weak section: {w}" for w in (vr.get("weak_sections") or [])])
    issues_list = [x for x in issues_list if x]
    proposed_sections = _proposed_sections_for_readme(vr) if isinstance(vr, dict) else []

    proposal = {
        "action": action_type,
        "title": "Repository documentation update proposal",
        "description": (
            f"Draft documentation update for {top['repo']} ({top['doc_file']})"
            if top
            else "Draft documentation update from current repo_pulse findings"
        ),
        "approval_required": approval_required,
        "action_classification": classification,
        "target_file": top.get("doc_file") if top else target_file,
        "reason": top.get("issue_found") if top else "No focused finding available in current snapshot",
        "proposed_change_summary": top.get("recommended_update") if top else "Prepare README status/setup/maintenance updates",
        "issues": issues_list,
        "missing_sections": list(vr.get("missing_sections") or []) if isinstance(vr, dict) else [],
        "weak_sections": list(vr.get("weak_sections") or []) if isinstance(vr, dict) else [],
        "proposed_sections": proposed_sections,
        "policy_reasoning": "Structured against README_POLICY required sections and README_RULES (non-empty, no placeholders, actionable commands).",
        "before_outline": [
            "Current README may be missing, stale, or inconsistent with recent repo activity.",
            "Sections likely lacking ownership, run instructions, or current status.",
        ],
        "after_outline": [
            "README includes current purpose/status, setup/run instructions, and ownership.",
            "Known caveats and maintenance notes aligned to current repo pulse signals.",
        ],
        "patch_preview": (
            f"- Target: {top['doc_file']}\n- Planned edits: {top['recommended_update']}\n- Verification: {top['suggested_verification']}"
            if top
            else "- No concrete file selected; choose target repo/file first."
        ),
        "verification_steps": [
            "Run local docs lint/check (if present) and open README for sanity review.",
            "Rebuild prepared context repo_pulse and verify docs freshness signals improve.",
            "Confirm no unrelated file changes are included before approval execution.",
        ],
        "approval_request_compatible": {
            "file_path": top.get("doc_file") if top else (target_file or "README.md"),
            "action_type": action_type,
            "reason": top.get("issue_found") if top else "docs cleanup proposal",
            "risk_level": "medium",
        },
        "source_evidence_paths": list(plan.get("source_paths") or []),
        "missing_data": list(plan.get("missing_data") or []),
        "no_direct_write_performed": True,
        "generated_from": "repo_pulse+policy",
        "readme_validation": vr,
        "plan_snapshot": {"priority_score": top.get("priority_score")} if top else {},
    }
    return proposal
