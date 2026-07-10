"""
Phase 8 — Repo-level documentation scoring, multi-file workplans, consistency checks, batch proposals.

Read-only: no file writes. Deterministic scoring and checks (no LLM, no worker).
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from brain.prepared_context.loader import load_snapshot_fresh
from brain.repo_docs_maintainer import _discover_policy_docs, _validate_aux_docs
from brain.repo_doc_validation import validate_readme

_MAX_DOCS_FILES = 25
_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_BACKTICK_PATH_RE = re.compile(r"`([^`]+\.(?:md|py|sh|ps1|json|ya?ml|toml))`", re.I)
_CMD_PATH_RE = re.compile(r"(?:^|\s)([\w./\\-]+\.(?:py|sh|ps1))(?:\s|$)", re.MULTILINE)


def _pulse_row_for_path(repo_path: Path) -> dict[str, Any] | None:
    rp = load_snapshot_fresh("repo_pulse")
    if not isinstance(rp, dict):
        return None
    data = rp.get("data") if isinstance(rp.get("data"), dict) else {}
    repos = list(data.get("repos") or [])
    target = str(repo_path.resolve())
    for row in repos:
        if not isinstance(row, dict):
            continue
        p = str(row.get("path") or "")
        if not p:
            continue
        try:
            if Path(p).resolve() == Path(target).resolve():
                return row
        except OSError:
            if p.rstrip("\\/").lower() == target.rstrip("\\/").lower():
                return row
    return None


def _grade_from_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _collect_markdown_files(repo_root: Path) -> list[Path]:
    out: list[Path] = []
    docs = repo_root / "docs"
    if docs.is_dir():
        try:
            for p in sorted(docs.rglob("*.md")):
                if p.is_file() and "node_modules" not in str(p).lower():
                    out.append(p)
                    if len(out) >= _MAX_DOCS_FILES:
                        break
        except OSError:
            pass
    readme = repo_root / "README.md"
    if readme.is_file() and readme not in out:
        out.insert(0, readme)
    return out[:_MAX_DOCS_FILES]


def _resolve_ref(repo_root: Path, ref: str) -> Path | None:
    ref = ref.strip().split("#", 1)[0].strip()
    if not ref or ref.startswith(("http://", "https://", "mailto:")):
        return None
    if ref.startswith("/"):
        return None
    # strip angle brackets
    ref = ref.strip("<>")
    try:
        cand = (repo_root / ref).resolve()
        root_res = repo_root.resolve()
        if root_res in cand.parents or cand == root_res:
            return cand
    except OSError:
        return None
    return None


def check_repo_docs_consistency(repo_path: str | Path) -> dict[str, Any]:
    """
    Lightweight deterministic checks: markdown links, backticked paths, obvious duplicates, template refs.
    """
    root = Path(repo_path)
    issues: list[dict[str, Any]] = []
    if not root.is_dir():
        return {"ok": False, "repo_path": str(repo_path), "issues": [{"type": "invalid_root", "detail": "not a directory"}]}

    md_files = _collect_markdown_files(root)
    seen_fences: dict[str, list[str]] = {}

    for md_path in md_files:
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = str(md_path.relative_to(root)) if md_path.is_relative_to(root) else str(md_path)

        for m in _LINK_RE.finditer(text):
            raw = m.group(1).strip()
            target = _resolve_ref(root, raw)
            if target is not None and not target.is_file() and not target.is_dir():
                issues.append(
                    {
                        "type": "missing_link_target",
                        "source_file": rel,
                        "reference": raw,
                        "detail": f"Linked path does not exist: {raw}",
                    }
                )

        for m in _BACKTICK_PATH_RE.finditer(text):
            raw = m.group(1).strip()
            if raw.startswith(("http://", "https://")):
                continue
            target = _resolve_ref(root, raw)
            if target is not None and not target.is_file():
                issues.append(
                    {
                        "type": "missing_backtick_path",
                        "source_file": rel,
                        "reference": raw,
                        "detail": f"Backticked path not found: {raw}",
                    }
                )

        low = text.lower()
        if "docs/templates/" in low or "readme_template" in low:
            tpl = root / "docs" / "templates" / "README_TEMPLATE.md"
            if not tpl.is_file():
                issues.append(
                    {
                        "type": "stale_template_reference",
                        "source_file": rel,
                        "reference": "docs/templates/README_TEMPLATE.md",
                        "detail": "Document references templates but README_TEMPLATE.md is missing.",
                    }
                )

        for fence in re.finditer(r"```(?:bash|sh|shell|powershell|pwsh)?\s*\n(.*?)```", text, re.DOTALL | re.I):
            block = fence.group(1).strip()
            if len(block) < 12:
                continue
            key = re.sub(r"\s+", " ", block.lower()[:200])
            if key.startswith(("npm ", "pip ", "yarn ", "pnpm ")):
                seen_fences.setdefault(key, []).append(rel)

    for key, paths in seen_fences.items():
        if len(paths) >= 2:
            issues.append(
                {
                    "type": "duplicate_setup_command",
                    "source_file": paths[0],
                    "reference": key[:120],
                    "detail": f"Same fenced install/run block appears in: {', '.join(paths[:5])}",
                }
            )

    # README entrypoints: simple `./script` or `python path` existence
    readme = root / "README.md"
    if readme.is_file():
        try:
            rtext = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            rtext = ""
        for m in _CMD_PATH_RE.finditer(rtext):
            token = m.group(1).strip().strip("`\"'")
            if not token.startswith((".", "scripts/", "bin/", "tools/")):
                continue
            tpath = _resolve_ref(root, token.lstrip("./"))
            if tpath is not None and not tpath.is_file():
                issues.append(
                    {
                        "type": "missing_readme_entrypoint",
                        "source_file": "README.md",
                        "reference": token,
                        "detail": "README mentions a script/path that does not exist at that relative path.",
                    }
                )

    return {"ok": True, "repo_path": str(root.resolve()), "issues": issues}


def assess_repo_documentation(
    repo_path: str | Path,
    repo_id: str | None = None,
    *,
    repo_pulse_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Deterministic 0–100 score with grade and structured evidence.
    """
    root = Path(repo_path)
    rid = repo_id or root.name
    row = repo_pulse_row if repo_pulse_row is not None else _pulse_row_for_path(root)

    required_docs_present: list[str] = []
    missing_docs: list[str] = []
    invalid_docs: list[str] = []
    stale_docs: list[str] = []
    weak_sections_agg: list[str] = []
    evidence_items: list[dict[str, Any]] = []

    if not root.is_dir():
        return {
            "ok": False,
            "repo_id": rid,
            "repo_path": str(repo_path),
            "score_0_to_100": 0,
            "grade": "F",
            "required_docs_present": [],
            "missing_docs": ["<repo path invalid>"],
            "invalid_docs": [],
            "stale_docs": [],
            "weak_sections": [],
            "consistency_issues": [],
            "risk_level": "high",
            "top_recommendations": ["Fix or provide a valid repository root path."],
            "evidence_items": [{"type": "error", "path": str(repo_path), "detail": "not a directory"}],
        }

    readme = root / "README.md"
    if readme.is_file():
        required_docs_present.append("README.md")
        vr = validate_readme(readme)
        evidence_items.append({"type": "readme_validation", "path": str(readme), "detail": vr})
        if not vr.get("is_valid"):
            invalid_docs.append(str(readme))
        for w in vr.get("weak_sections") or []:
            weak_sections_agg.append(f"README:{w}")
        for m in vr.get("missing_sections") or []:
            if m not in ("<file missing>", "<empty file>"):
                weak_sections_agg.append(f"README:missing:{m}")
        # Bucket scores
        if vr.get("is_valid"):
            b_readme = 35
        else:
            miss = len([x for x in vr.get("missing_sections") or [] if x not in ("<file missing>", "<empty file>")])
            weakn = len(vr.get("weak_sections") or [])
            b_readme = max(0, 35 - min(28, 7 * miss + 3 * weakn))

        miss_s = set(vr.get("missing_sections") or [])
        weak_s = set(vr.get("weak_sections") or [])
        trio = ("setup", "configuration", "usage")
        trio_ok = sum(1 for k in trio if k not in miss_s and not any(x.startswith(k) for x in weak_s))
        b_clarity = int(round(20 * trio_ok / 3))

        ver_ok = "verification" not in miss_s and not any(x.startswith("verification") for x in weak_s)
        troup = any("troubleshooting" in x for x in weak_s) or "troubleshooting" in miss_s
        b_verify = 10 if ver_ok else 4
        if not troup and (root / "README.md").exists():
            b_verify = min(15, b_verify + 5)

        aux = _validate_aux_docs(root)
        disc = _discover_policy_docs(root)
        has_aux = bool(disc["runbooks"] or disc["system_maps"])
        if not has_aux:
            b_aux = 12
        else:
            ok_rb = sum(1 for x in aux["runbooks"] if x.get("is_valid"))
            ok_sm = sum(1 for x in aux["system_maps"] if x.get("is_valid"))
            n = max(1, len(aux["runbooks"]) + len(aux["system_maps"]))
            b_aux = int(round(15 * (ok_rb + ok_sm) / n))
            for rb in aux["runbooks"]:
                if not rb.get("is_valid"):
                    invalid_docs.append(rb.get("path", ""))
            for sm in aux["system_maps"]:
                if not sm.get("is_valid"):
                    invalid_docs.append(sm.get("path", ""))

        b_fresh = 8
        if isinstance(row, dict):
            if row.get("readme_fresh"):
                b_fresh += 5
            if not row.get("stale"):
                b_fresh += 4
            if int(row.get("todo_fixme_count") or 0) < 15:
                b_fresh += 3
        b_fresh = min(15, b_fresh)

        if isinstance(row, dict) and not row.get("readme_fresh"):
            stale_docs.append("README.md (repo_pulse: readme_fresh=false)")
        if isinstance(row, dict) and row.get("stale"):
            stale_docs.append("repository (repo_pulse: stale=true)")

    else:
        missing_docs.append("README.md")
        b_readme = 0
        b_clarity = 0
        b_verify = 0
        b_aux = 8
        b_fresh = 8
        if isinstance(row, dict):
            if row.get("readme_fresh"):
                b_fresh += 4
            if not row.get("stale"):
                b_fresh += 3
        b_fresh = min(15, b_fresh)
        vr = None

    consistency = check_repo_docs_consistency(root)
    c_issues = list(consistency.get("issues") or [])
    consistency_penalty = min(15, 3 * len(c_issues))
    raw = b_readme + b_clarity + b_verify + b_aux + b_fresh
    score = max(0, min(100, raw - consistency_penalty))

    grade = _grade_from_score(score)
    if score < 50 or len(c_issues) >= 6:
        risk = "high"
    elif score < 70 or len(invalid_docs) >= 2 or len(c_issues) >= 2:
        risk = "medium"
    else:
        risk = "low"

    recs: list[str] = []
    if missing_docs:
        recs.append("Add README.md with required policy sections and verification steps.")
    if invalid_docs:
        recs.append("Fix README (and listed aux docs) to satisfy policy validation.")
    if c_issues:
        recs.append("Repair broken internal links and README entrypoint references.")
    if isinstance(row, dict) and not row.get("readme_fresh"):
        recs.append("Refresh README timestamps/content to match recent repo activity.")
    if not recs:
        recs.append("Keep docs aligned with code; re-run assessment after large changes.")
    recs = recs[:8]

    evidence_items.append({"type": "consistency_scan", "path": str(root), "detail": {"issue_count": len(c_issues)}})

    return {
        "ok": True,
        "repo_id": rid,
        "repo_path": str(root.resolve()),
        "score_0_to_100": score,
        "grade": grade,
        "required_docs_present": required_docs_present,
        "missing_docs": missing_docs,
        "invalid_docs": [x for x in invalid_docs if x],
        "stale_docs": stale_docs,
        "weak_sections": weak_sections_agg[:40],
        "consistency_issues": c_issues,
        "risk_level": risk,
        "top_recommendations": recs[:5],
        "evidence_items": evidence_items,
        "_score_breakdown": {
            "readme_validity_cap35": b_readme,
            "setup_config_usage_cap20": b_clarity,
            "verification_troubleshooting_cap15": b_verify,
            "runbook_system_map_cap15": b_aux,
            "freshness_cap15": b_fresh,
            "consistency_penalty": consistency_penalty,
        },
    }


def build_repo_docs_workplan(
    repo_path: str | Path,
    repo_id: str | None = None,
) -> dict[str, Any]:
    """Ordered multi-file documentation tasks derived from assessment + consistency."""
    root = Path(repo_path)
    rid = repo_id or root.name
    assessment = assess_repo_documentation(root, repo_id=rid)
    tasks: list[dict[str, Any]] = []
    if not assessment.get("ok"):
        return {
            "ok": False,
            "repo_id": rid,
            "repo_path": str(repo_path),
            "ordered_tasks": [],
            "source": "assessment_failed",
        }

    def _task(
        task_id: str,
        files: list[str],
        issue_type: str,
        proposed_fix: str,
        risk: str,
        effort: str,
        verify: list[str],
    ) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "affected_files": files,
            "issue_type": issue_type,
            "proposed_fix": proposed_fix,
            "approval_required": True,
            "risk_level": risk,
            "estimated_effort": effort,
            "verification_steps": verify,
        }

    if assessment.get("missing_docs"):
        tasks.append(
            _task(
                "readme-create",
                [str(root / "README.md")],
                "missing_readme",
                "Create README.md using docs/templates/README_TEMPLATE.md as a structural guide.",
                "medium",
                "large",
                ["Open new README in editor", "Run assess_repo_documentation again"],
            )
        )

    readme_p = root / "README.md"
    if readme_p.is_file():
        vr = validate_readme(readme_p)
        if not vr.get("is_valid"):
            tasks.append(
                _task(
                    "readme-policy",
                    [str(readme_p)],
                    "readme_policy",
                    "; ".join(vr.get("suggestions") or [])[:500] or "Align README with README_POLICY required sections.",
                    "medium",
                    "medium",
                    ["pytest tests/test_repo_doc_policy.py -q", "Re-run documentation assessment"],
                )
            )

    aux = _validate_aux_docs(root)
    for rb in aux.get("runbooks") or []:
        if not rb.get("is_valid"):
            p = rb.get("path") or ""
            tasks.append(
                _task(
                    f"runbook-{hash(p) % 10000}",
                    [p],
                    "runbook_policy",
                    "Bring runbook in line with RUNBOOK_POLICY (purpose, steps, expected result, failure handling).",
                    "low",
                    "small",
                    ["Peer review runbook", "Dry-walk steps on staging"],
                )
            )
    for sm in aux.get("system_maps") or []:
        if not sm.get("is_valid"):
            p = sm.get("path") or ""
            tasks.append(
                _task(
                    f"sysmap-{hash(p) % 10000}",
                    [p],
                    "system_map_policy",
                    "Expand system map: components, data flow, integration points.",
                    "low",
                    "small",
                    ["Architecture review with owner"],
                )
            )

    # Group consistency issues by source file
    by_file: dict[str, list[dict[str, Any]]] = {}
    for issue in assessment.get("consistency_issues") or []:
        sf = str(issue.get("source_file") or "unknown")
        by_file.setdefault(sf, []).append(issue)

    for sf, iss in by_file.items():
        paths = [str(root / sf)] if not sf.startswith(str(root)) else [sf]
        tasks.append(
            _task(
                f"consistency-{hash(sf) % 100000}",
                paths,
                "consistency",
                f"Fix {len(iss)} broken reference(s) or duplicate blocks in {sf}.",
                "medium" if len(iss) > 2 else "low",
                "small" if len(iss) < 3 else "medium",
                ["grep referenced paths", "Open links in editor and correct paths"],
            )
        )

    return {
        "ok": True,
        "repo_id": rid,
        "repo_path": str(root.resolve()),
        "ordered_tasks": tasks,
        "assessment_summary": {
            "score_0_to_100": assessment.get("score_0_to_100"),
            "grade": assessment.get("grade"),
            "risk_level": assessment.get("risk_level"),
        },
        "source": "repo_pulse+local_scan",
    }


def create_repo_docs_batch_proposal(
    repo_path: str | Path,
    selected_tasks: list[str] | None = None,
    *,
    repo_id: str | None = None,
) -> dict[str, Any]:
    """
    Batch proposal for multiple doc tasks. No file writes.
    """
    root = Path(repo_path)
    rid = repo_id or root.name
    wp = build_repo_docs_workplan(root, repo_id=rid)
    tasks = list(wp.get("ordered_tasks") or [])
    if selected_tasks:
        sel = set(selected_tasks)
        tasks = [t for t in tasks if t.get("task_id") in sel]
    if not tasks:
        tasks = list(wp.get("ordered_tasks") or [])

    target_files = sorted({f for t in tasks for f in t.get("affected_files") or []})
    proposal_id = f"docs-batch-{uuid.uuid4().hex[:12]}"

    proposed_changes: list[dict[str, Any]] = []
    grouped_sections: list[dict[str, Any]] = []
    for t in tasks:
        proposed_changes.append(
            {
                "task_id": t.get("task_id"),
                "files": t.get("affected_files"),
                "summary": t.get("proposed_fix"),
                "issue_type": t.get("issue_type"),
            }
        )
        grouped_sections.append(
            {
                "group": t.get("issue_type"),
                "task_id": t.get("task_id"),
                "outline": [
                    t.get("proposed_fix") or "",
                    f"Risk: {t.get('risk_level')}, effort: {t.get('estimated_effort')}",
                ],
            }
        )

    n_files = len(target_files)
    risk = "high" if n_files >= 5 or len(tasks) >= 6 else "medium" if n_files >= 2 else "low"

    return {
        "proposal_id": proposal_id,
        "repo_id": rid,
        "repo_path": str(root.resolve()) if root.is_dir() else str(repo_path),
        "target_files": target_files,
        "proposed_changes": proposed_changes,
        "grouped_sections": grouped_sections,
        "approval_required": True,
        "action_classification": "modifies-files-or-state",
        "no_direct_write_performed": True,
        "verification_steps": [
            "Review every listed file; apply edits only after approval.",
            "Re-run assess_repo_documentation and check_repo_docs_consistency.",
            "Run project test or smoke command documented in README.",
        ],
        "risk_level": risk,
        "task_count": len(tasks),
    }


def resolve_repo_docs_target(message: str, default_root: Path | None = None) -> tuple[Path | None, str | None, str]:
    """
    Resolve (repo_path, repo_id, error_message) from user message + repo_pulse.
    """
    msg = (message or "").strip()
    if not msg:
        if default_root and default_root.is_dir():
            return default_root, default_root.name, ""
        return None, None, "empty_message"

    m = re.search(r"([A-Za-z]:[/\\][^\n|]+)", msg)
    if m:
        p = Path(m.group(1).strip().rstrip(".,);"))
        if p.is_dir():
            return p, p.name, ""

    rp = load_snapshot_fresh("repo_pulse")
    data = rp.get("data") if isinstance(rp, dict) else {}
    repos = list(data.get("repos") or []) if isinstance(data, dict) else []
    low = msg.lower()
    for row in repos:
        if not isinstance(row, dict):
            continue
        name = str(row.get("repo") or "")
        if name and name.lower() in low:
            pp = row.get("path")
            if pp and Path(pp).is_dir():
                return Path(pp), name, ""

    if default_root and default_root.is_dir():
        if "ai-lab" in low or "ai lab" in low or "documentation score" in low or "docs a grade" in low:
            return default_root, default_root.name, ""
        # generic score / workplan without naming a repo → default root
        if any(
            w in low
            for w in (
                "score repo documentation",
                "repo docs workplan",
                "batch docs proposal",
                "docs consistency",
                "updated together",
            )
        ):
            return default_root, default_root.name, ""

    return None, None, "repo_not_resolved_from_message"
