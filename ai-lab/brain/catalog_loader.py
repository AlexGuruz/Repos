"""
Read-only load of ai-lab-governance system catalog (components, environments, repo paths).
Used by the orchestrator for grounded answers; does not mutate catalog data.

Resolution order for governance root:
  1. AI_LAB_GOVERNANCE_ROOT
  2. Sibling of ai-lab repo: <ai-lab>/../ai-lab-governance
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_CACHE: tuple[float | None, dict[str, Any]] | None = None


def _ai_lab_root() -> Path:
    return Path(__file__).resolve().parents[1]


def governance_root() -> Path | None:
    env = os.environ.get("AI_LAB_GOVERNANCE_ROOT", "").strip()
    if env:
        p = Path(env)
        return p if p.is_dir() else None
    guess = _ai_lab_root().parent / "ai-lab-governance"
    return guess if guess.is_dir() else None


def load_catalog(*, force: bool = False) -> dict[str, Any] | None:
    """Load components, environments, repos. None if governance or files missing."""
    global _CACHE
    root = governance_root()
    if not root:
        return None
    comp_path = root / "registry" / "components.yaml"
    if not comp_path.is_file():
        return None
    try:
        mtime = comp_path.stat().st_mtime
    except OSError:
        return None
    if not force and _CACHE is not None and _CACHE[0] == mtime:
        return _CACHE[1]

    try:
        import yaml
    except ImportError:
        return None

    with comp_path.open(encoding="utf-8") as f:
        doc = yaml.safe_load(f)

    env_path = root / "registry" / "environments.yaml"
    environments: dict[str, dict[str, Any]] = {}
    if env_path.is_file():
        with env_path.open(encoding="utf-8") as f:
            ed = yaml.safe_load(f) or {}
        for e in ed.get("environments") or []:
            if isinstance(e, dict) and e.get("id"):
                environments[str(e["id"])] = e

    reg_path = root / "registry" / "repo_registry.json"
    repos: dict[str, dict[str, Any]] = {}
    if reg_path.is_file():
        with reg_path.open(encoding="utf-8") as f:
            rd = json.load(f)
        for r in rd.get("repos") or []:
            if isinstance(r, dict) and r.get("repo_id"):
                repos[str(r["repo_id"])] = r

    data: dict[str, Any] = {
        "governance_root": str(root),
        "components_by_id": {},
        "components_by_repo": {},
        "environments": environments,
        "repos": repos,
    }
    for c in doc.get("components") or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id")
        if not cid:
            continue
        data["components_by_id"][str(cid)] = c
        pr = c.get("primary_repo")
        if pr:
            data["components_by_repo"].setdefault(str(pr), []).append(c)

    _CACHE = (mtime, data)
    return data


def get_component(component_id: str) -> dict[str, Any] | None:
    d = load_catalog()
    if not d:
        return None
    return d["components_by_id"].get(component_id)


def get_environment(environment_id: str) -> dict[str, Any] | None:
    d = load_catalog()
    if not d:
        return None
    return d["environments"].get(environment_id)


def components_for_repo(repo_id: str) -> list[dict[str, Any]]:
    d = load_catalog()
    if not d:
        return []
    return list(d["components_by_repo"].get(repo_id, []))


def authority_for_domain(component: dict[str, Any], domain: str) -> dict[str, Any] | None:
    auth = component.get("authority") or {}
    b = auth.get(domain)
    return b if isinstance(b, dict) else None


def capability_summary(component: dict[str, Any]) -> str:
    caps = component.get("capabilities") or {}
    if not isinstance(caps, dict):
        return "(none)"
    parts = [f"{k}={v}" for k, v in sorted(caps.items())]
    return ", ".join(parts) if parts else "(none)"


def owners_summary(component: dict[str, Any]) -> dict[str, str]:
    return {
        "code_owner": str(component.get("code_owner") or ""),
        "deploy_owner": str(component.get("deploy_owner") or ""),
        "runtime_owner": str(component.get("runtime_owner") or ""),
        "approval_owner": str(component.get("approval_owner") or ""),
    }


def evidence_status_summary(component: dict[str, Any]) -> tuple[str, str | None]:
    """Human-readable evidence rollup + last_verified_at."""
    ev = component.get("evidence") or {}
    lines: list[str] = []
    if isinstance(ev, dict):
        for k, row in ev.items():
            if not isinstance(row, dict):
                continue
            req = row.get("required_for_lifecycle")
            st = row.get("status")
            ob = row.get("observed_at")
            lines.append(f"{k}: required={req} status={st} observed_at={ob}")
    return "; ".join(lines) if lines else "(no evidence keys)", component.get("last_verified_at")


def _token_boundary_match(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    pat = rf"(?:^|[^a-z0-9-]){re.escape(needle)}(?:$|[^a-z0-9-])"
    return re.search(pat, haystack) is not None


def _matches_component(msg_lower: str, cid: str, c: dict[str, Any]) -> bool:
    if _token_boundary_match(msg_lower, cid):
        return True
    pr = str(c.get("primary_repo") or "")
    if pr and _token_boundary_match(msg_lower, pr):
        return True
    dn = str(c.get("display_name") or "").lower()
    if len(dn) >= 6 and dn in msg_lower:
        return True
    # Short aliases
    aliases = {
        "secrets-config-plane": (
            "secrets plane",
            "secrets config",
            "lab-secrets",
            "secret manager",
            "secrets repo",
        ),
        "command-center": ("command center", "command-center"),
        "ai-lab": ("ai lab", "ai-lab"),
        "worker": ("worker rig", "worker-rig"),
        "geomapper": ("geomapper app",),
    }
    for phrase in aliases.get(cid, ()):
        if phrase in msg_lower:
            return True
    return False


def matching_components(message: str) -> list[dict[str, Any]]:
    d = load_catalog()
    if not d:
        return []
    msg_lower = (message or "").lower()
    explicit = re.findall(r"@catalog\s+([a-z0-9][a-z0-9-]*)", msg_lower)
    if explicit:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in explicit:
            c = d["components_by_id"].get(raw)
            if c and raw not in seen:
                out.append(c)
                seen.add(raw)
        if out:
            return out
    out = []
    seen: set[str] = set()
    for cid, c in d["components_by_id"].items():
        if _matches_component(msg_lower, cid, c) and cid not in seen:
            out.append(c)
            seen.add(cid)
    return out


def format_component_grounding(c: dict[str, Any]) -> str:
    """Structured text for LLM / operator (one component)."""
    cid = c.get("id", "?")
    lines = [
        f"### Catalog: `{cid}` ({c.get('display_name', '')})",
        f"- **lifecycle_state**: {c.get('lifecycle_state')} (capabilities are authoritative for 'partial'; 'built' requires passing lifecycle evidence in catalog)",
        f"- **primary_repo**: {c.get('primary_repo')}",
        f"- **capabilities**: {capability_summary(c)}",
        f"- **owners**: code={c.get('code_owner')}; deploy={c.get('deploy_owner')}; "
        f"runtime={c.get('runtime_owner')}; approval={c.get('approval_owner')}",
    ]
    envs = c.get("environments") or {}
    if isinstance(envs, dict) and envs:
        dep_parts = []
        for eid, row in envs.items():
            if isinstance(row, dict):
                dep_parts.append(f"{eid}: deployed={row.get('deployed')}")
        lines.append(f"- **environments**: {', '.join(dep_parts)}")
    for domain in (
        "api_contract",
        "runtime_config",
        "deployment_topology",
        "operator_procedure",
        "implementation_behavior",
    ):
        b = authority_for_domain(c, domain)
        if b:
            lines.append(
                f"- **authority.{domain}**: {b.get('source_kind')} → `{b.get('canonical_ref')}`"
            )
    ev_text, lva = evidence_status_summary(c)
    lines.append(f"- **evidence**: {ev_text}")
    lines.append(f"- **last_verified_at**: {lva}")
    return "\n".join(lines)


def format_catalog_grounding_for_message(message: str, max_chars: int = 4500) -> str:
    """
    If the user message mentions known components/repos, inject catalog facts.
    Read-only; safe to prepend to evidence or system prompt.
    """
    matches = matching_components(message)
    if not matches:
        return ""
    header = (
        "## Lab system catalog (authoritative; do not invent)\n"
        "Use this for: what is authoritative per domain, lifecycle/partial vs built, "
        "owners, environments, primary repo. Repo risk class is **not** here (see governance repo_classes).\n"
    )
    body = "\n\n".join(format_component_grounding(c) for c in matches[:4])
    text = header + "\n" + body
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…(truncated)"
    return text


def infer_component_from_file_path(file_path: str) -> dict[str, Any] | None:
    """Best-effort: map an absolute/relative file path to a primary component (for approval payloads)."""
    d = load_catalog()
    if not d or not file_path:
        return None
    try:
        target = Path(file_path).resolve()
    except OSError:
        target = Path(file_path)
    best: tuple[int, dict[str, Any]] | None = None
    for rid, meta in d["repos"].items():
        p = meta.get("path")
        if not p:
            continue
        try:
            root = Path(str(p).replace("\\", "/")).resolve()
        except OSError:
            root = Path(str(p))
        try:
            target.relative_to(root)
        except ValueError:
            continue
        # Longest root wins
        key = len(str(root))
        comps = d["components_by_repo"].get(rid, [])
        for c in comps:
            if best is None or key > best[0]:
                best = (key, c)
    return best[1] if best else None


def format_approval_catalog_attachment(file_path: str) -> str:
    """Short block to merge into approval reason / payload when path is known."""
    c = infer_component_from_file_path(file_path)
    if not c:
        return ""
    lines = [
        f"[catalog] component_id={c.get('id')}",
        f"lifecycle={c.get('lifecycle_state')} capabilities={capability_summary(c)}",
        f"owners approval={c.get('approval_owner')} code={c.get('code_owner')}",
        f"primary_repo={c.get('primary_repo')}",
    ]
    b = authority_for_domain(c, "api_contract")
    if b:
        lines.append(f"authority.api_contract={b.get('source_kind')}: {b.get('canonical_ref')}")
    return "\n".join(lines)
