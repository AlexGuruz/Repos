"""
Phase 4 — integration inventory generator (visibility + drift detection only).

Produces JSON + markdown under state/integration_inventory/ and docs/.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCAN_EXTENSIONS = {".py", ".ps1", ".js", ".jsx", ".ts", ".tsx"}
SKIP_DIR_NAMES = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".git",
        ".pytest_cache",
        "coverage",
        "tests",
    }
)

WRITE_HINTS = re.compile(
    r"\b(open\s*\([^)]*['\"]w|\.write_text|\.write_bytes|shutil\.(copy|move|rmtree)|"
    r"subprocess\.|os\.remove|os\.unlink|requests\.(post|put|patch|delete)|"
    r"httpx\.(post|put|patch|delete)|smtplib|sms|calendar\.|sqlite3|"
    r"chromadb|promote|index_repo|write_sheet|restart_service|modify_registry)\b",
    re.I,
)
READ_ONLY_HINTS = re.compile(
    r"\b(read_only|GET\b|\.get\s*\(|list_dir|glob\(|read_text|json\.loads)\b",
    re.I,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ai_lab_root() -> Path:
    """ai-lab repo root (parent of `brain/`)."""
    return Path(__file__).resolve().parents[2]


def _iter_files(root: Path, exts: set[str]) -> Iterable[Path]:
    if not root.is_dir():
        return
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        yield p


def _rel_posix(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_snippet(path: Path, limit: int = 96_000) -> str:
    try:
        data = path.read_bytes()[:limit]
        return data.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _guess_purpose(text: str) -> str:
    m = re.search(r'^\s*"""([^"]{0,200})', text, re.M)
    if m:
        return m.group(1).strip().replace("\n", " ")
    m = re.search(r"^\s*#\s*(.{12,200})", text, re.M)
    if m:
        return m.group(1).strip()[:200]
    return "unspecified"


def _load_growflow_inventory(ai_lab: Path) -> list[dict[str, Any]]:
    p = ai_lab / "state" / "integration_inventory" / "growflow_runners.json"
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    rows = data.get("scripts") or []
    return [r for r in rows if isinstance(r, dict)]


def _load_registry_scripts(ai_lab: Path) -> list[dict[str, Any]]:
    p = ai_lab / "registry" / "scripts.json"
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [x for x in data if isinstance(x, dict)]


def _load_brain_tool_registry(ai_lab: Path) -> list[dict[str, Any]]:
    """Import brain.tool_registry without requiring full deps."""
    import importlib.util
    import sys

    root_s = str(ai_lab.resolve())
    if root_s not in sys.path:
        sys.path.insert(0, root_s)

    path = ai_lab / "brain" / "tool_registry.py"
    spec = importlib.util.spec_from_file_location("tool_registry_dyn", path)
    if spec is None or spec.loader is None:
        return []
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return []
    fn = getattr(mod, "load_tool_registry", None)
    if callable(fn):
        try:
            out = fn()
            return list(out) if isinstance(out, list) else []
        except Exception:
            return []
    return []


def _parse_ps1_python_targets(text: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r'python\s+["\']?([^"\'\s]+\.py)', text, re.I):
        out.append(m.group(1).replace("\\", "/"))
    return out


def _schedule_keys_for_target(ai_lab: Path, target: str) -> list[str]:
    """Keys used to attach PowerShell wrappers to inventory script rows."""
    t = target.replace("\\", "/")
    keys = [t, Path(t).name]
    name = Path(t).name
    cand = ai_lab / "scripts" / name
    if cand.is_file():
        keys.append(_rel_posix(ai_lab, cand))
    return list(dict.fromkeys(keys))


def _collect_ps1_triggers(ai_lab: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Return trigger rows + map script_path -> [scheduling wrapper ps1]."""
    triggers: list[dict[str, Any]] = []
    scheduled_by: dict[str, list[str]] = defaultdict(list)
    for root in (
        ai_lab / "scripts",
        ai_lab / "command-center" / "command-center" / "scripts",
        ai_lab / "email_sorter" / "scripts",
    ):
        if not root.is_dir():
            continue
        for ps1 in root.rglob("*.ps1"):
            if any(x in ps1.parts for x in SKIP_DIR_NAMES):
                continue
            rel = _rel_posix(ai_lab, ps1)
            text = _read_snippet(ps1, 64_000)
            targets = _parse_ps1_python_targets(text)
            tname = ps1.name
            triggers.append(
                {
                    "trigger_name": tname,
                    "trigger_type": "powershell_wrapper",
                    "target_path_or_function": targets[0] if targets else rel,
                    "interval_if_known": None,
                    "last_run_visible": False,
                    "output_consumed_by": [],
                    "status": "partial" if targets else "missing_visibility",
                    "reasons": [f"resolved_from={rel}"],
                }
            )
            for t in targets:
                for key in _schedule_keys_for_target(ai_lab, t):
                    scheduled_by[key].append(rel)
    return triggers, scheduled_by


def _lifespan_triggers() -> list[dict[str, Any]]:
    return [
        {
            "trigger_name": "fastapi_lifespan_background",
            "trigger_type": "backend_lifespan",
            "target_path_or_function": "command-center/command-center/backend/main.py:lifespan",
            "interval_if_known": "startup + shutdown hooks",
            "last_run_visible": True,
            "output_consumed_by": [
                "services/repo_watcher.py",
                "services/nvidia_poller.py",
                "services/prepared_context_refresher.py",
                "services/repo_index_coordinator.py",
            ],
            "status": "wired",
            "reasons": ["Declared in FastAPI lifespan context manager"],
        },
        {
            "trigger_name": "prepared_context_policy_loop",
            "trigger_type": "backend_lifespan",
            "target_path_or_function": "services/prepared_context_refresher.py:run_prepared_context_refresher",
            "interval_if_known": "20s loop; per-type intervals in POLICIES (10–1440 min)",
            "last_run_visible": True,
            "output_consumed_by": ["state/prepared_context/*.json", "routers/prepared_context.py"],
            "status": "wired",
            "reasons": ["POLICIES tuple drives snapshot refresh cadence"],
        },
        {
            "trigger_name": "n8n_worker_automation_assumption",
            "trigger_type": "n8n_assumption",
            "target_path_or_function": "worker tunnel + n8n_trigger / worker_n8n_trigger tools",
            "interval_if_known": None,
            "last_run_visible": False,
            "output_consumed_by": [],
            "status": "assumption",
            "reasons": ["Not statically traced in this inventory; confirm in ops"],
        },
    ]


def _classify_local_script(rel: str, name: str, ext: str) -> str:
    r = rel.lower()
    if "command-center/command-center/frontend" in r:
        return "command_center_frontend"
    if "command-center/command-center/backend" in r:
        return "command_center_backend"
    if r.startswith("brain/prepared_context/"):
        return "prepared_context_builder" if name == "builders.py" else "runtime_service"
    if r.startswith("brain/"):
        return "runtime_service"
    if r.startswith("scripts/") or r.startswith("email_sorter/scripts/"):
        low = name.lower()
        if low.startswith(("_tmp", "_patch")) or "patch" in low:
            return "temp_probe"
        if low.startswith(("_probe", "_scan", "_check", "_dump", "_print", "_query")) or low.startswith(
            "probe_"
        ):
            return "diagnostic"
        if low.startswith("_") and ext == ".py":
            return "diagnostic"
        if ext == ".ps1":
            return "scheduled_script"
        return "cli_script"
    return "unknown"


def _side_effect_guesses(text: str) -> tuple[bool, bool, bool]:
    writes = bool(WRITE_HINTS.search(text))
    external = writes or bool(
        re.search(r"\b(https?://|api\.|openai|growflow|google|gmail|smtp)\b", text, re.I)
    )
    readish = bool(READ_ONLY_HINTS.search(text)) and not writes
    approval = writes or external
    if readish and not writes:
        approval = False
    return writes, external, approval


def _extract_script_path_mentions(text: str) -> set[str]:
    """Return `scripts/...py` paths and bare `*.py` script names mentioned in source."""
    out: set[str] = set()
    for m in re.finditer(r"(?:^|[\s\"\'\(])scripts/[\w./-]+\.py", text, re.M):
        frag = m.group(0)
        idx = frag.find("scripts/")
        if idx >= 0:
            out.add(frag[idx:].split()[0].strip("\"'"))
    for m in re.finditer(r"\b[\w][\w_-]{2,80}\.py\b", text):
        out.add(m.group(0))
    return out


def _build_reverse_refs(ai_lab: Path, script_basenames: set[str]) -> dict[str, list[str]]:
    """Map `scripts/*.py` basename -> referrers (regex path mentions; bounded file set)."""
    refs: dict[str, list[str]] = defaultdict(list)
    cc_back = ai_lab / "command-center" / "command-center" / "backend"
    ref_paths: list[Path] = []
    for sub in (
        ai_lab / "brain" / "prepared_context",
        ai_lab / "brain" / "orchestrator",
        ai_lab / "scripts",
        cc_back / "routers",
        cc_back / "services",
    ):
        if sub.is_dir():
            ref_paths.extend(p for p in _iter_files(sub, {".py"}))
        elif sub.is_file() and sub.suffix == ".py":
            ref_paths.append(sub)
    main_py = cc_back / "main.py"
    if main_py.is_file():
        ref_paths.append(main_py)
    seen: set[str] = set()
    for p in ref_paths:
        rel = _rel_posix(ai_lab, p)
        if rel in seen:
            continue
        seen.add(rel)
        text = _read_snippet(p, 48_000)
        mentions = _extract_script_path_mentions(text)
        for bn in script_basenames:
            if not bn:
                continue
            if bn in mentions or any(m.endswith("/" + bn) for m in mentions if m.startswith("scripts/")):
                refs[bn].append(rel)
    return refs


def _script_status(
    classification: str,
    refs: list[str],
    reg_tool: str | None,
    scheduled_wrappers: list[str],
    gf_notes: list[str],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if gf_notes:
        reasons.extend(gf_notes)
    if reg_tool:
        reasons.append(f"registered_tool={reg_tool}")
    if scheduled_wrappers:
        reasons.append(f"scheduled_by_wrappers={scheduled_wrappers[:5]}")
    if refs:
        reasons.append(f"referenced_by_count={len(refs)}")

    if classification in ("temp_probe", "diagnostic"):
        return "manual_only", reasons + ["probe/diagnostic — not promoted to wired automation by default"]
    if reg_tool:
        st = "wired" if refs or scheduled_wrappers else "partial"
        return st, reasons
    if scheduled_wrappers:
        return "partial", reasons + ["invoked from PowerShell wrapper; verify Task Scheduler"]
    if refs:
        return "partial", reasons
    if classification in ("command_center_backend", "command_center_frontend", "runtime_service"):
        return "wired", reasons + ["application/module surface"]
    if classification == "prepared_context_builder":
        return "wired", reasons + ["snapshot builder entrypoint"]
    if classification == "growflow_runner":
        return "manual_only", reasons + ["Growflow repo script — run on ops host"]
    if classification == "unknown":
        return "unknown_needs_review", reasons + ["heuristic unknown"]
    return "orphan_candidate", reasons + ["no registry, no schedule wrapper, no cross-ref hits"]


def generate_integration_inventory(
    ai_lab: Path | None = None,
    output_dir: Path | None = None,
    docs_path: Path | None = None,
) -> dict[str, Any]:
    ai_lab = ai_lab or _ai_lab_root()
    output_dir = output_dir or (ai_lab / "state" / "integration_inventory")
    docs_path = docs_path or (ai_lab / "docs" / "SCRIPT_TOOL_INVENTORY_AUTO.md")
    output_dir.mkdir(parents=True, exist_ok=True)

    scan_roots = [
        ai_lab / "scripts",
        ai_lab / "brain",
        ai_lab / "command-center" / "command-center" / "backend",
        ai_lab / "command-center" / "command-center" / "frontend" / "src",
    ]

    files: list[tuple[str, Path]] = []
    for root in scan_roots:
        for p in _iter_files(root, SCAN_EXTENSIONS):
            files.append((_rel_posix(ai_lab, p), p))

    script_basenames = {p.name for rel, p in files if rel.startswith("scripts/") and p.suffix == ".py"}
    reverse_by_basename = _build_reverse_refs(ai_lab, script_basenames)
    ps1_triggers, scheduled_by = _collect_ps1_triggers(ai_lab)
    triggers: list[dict[str, Any]] = _lifespan_triggers() + ps1_triggers

    registry_rows = _load_registry_scripts(ai_lab)
    brain_tools = _load_brain_tool_registry(ai_lab)
    brain_by_name = {t.get("name"): t for t in brain_tools if t.get("name")}

    reg_path_by_tool: dict[str, str] = {}
    for row in registry_rows:
        tn = row.get("tool_name")
        p = row.get("path")
        if tn and isinstance(p, str):
            reg_path_by_tool[str(tn)] = p

    growflow_rows = _load_growflow_inventory(ai_lab)

    scripts_out: list[dict[str, Any]] = []
    for rel, p in sorted(files, key=lambda x: x[0]):
        name = p.name
        ext = p.suffix.lower()
        text = _read_snippet(p, 32_000)
        cls = _classify_local_script(rel, name, ext)
        w, ext_side, appr_guess = _side_effect_guesses(text)
        refs = [x for x in reverse_by_basename.get(name, []) if x != rel][:40]
        sched = list(dict.fromkeys(scheduled_by.get(rel, []) + scheduled_by.get(name, [])))
        reg_tool: str | None = None
        for tn, rp in reg_path_by_tool.items():
            if not isinstance(rp, str):
                continue
            rp_norm = rp.replace("\\", "/")
            if rel == rp_norm or rel.endswith("/" + rp_norm) or rp_norm.endswith("/" + rel):
                reg_tool = tn
                break
        if reg_tool is None:
            for tn, rp in reg_path_by_tool.items():
                if isinstance(rp, str) and Path(rp.replace("\\", "/")).name == name:
                    reg_tool = tn
                    break

        prepared_ctx = rel in (
            "brain/prepared_context/builders.py",
            "scripts/build_prepared_context.py",
        ) or rel.startswith("scripts/refresh_prepared_context_")

        st, reasons = _script_status(cls, refs, reg_tool, sched, [])
        scripts_out.append(
            {
                "path": rel,
                "name": name,
                "extension": ext,
                "guessed_purpose": _guess_purpose(text),
                "classification": cls,
                "imported_by_or_referenced_by": refs,
                "scheduled_by": sched,
                "registered_tool_name": reg_tool,
                "prepared_context_source": prepared_ctx,
                "writes_state_guess": w,
                "external_side_effect_guess": ext_side,
                "approval_required_guess": appr_guess,
                "status": st,
                "reasons": reasons,
            }
        )

    for gr in growflow_rows:
        rel = gr.get("relative") or ""
        if not rel:
            continue
        gpath = f"../Growflow/{rel.replace(chr(92), '/')}"
        gcat = gr.get("category") or "unknown"
        gnotes = [f"growflow_runners.json: category={gcat}"]
        scripts_out.append(
            {
                "path": gpath,
                "name": Path(rel).name,
                "extension": ".py",
                "guessed_purpose": gr.get("notes") or "from growflow inventory",
                "classification": "growflow_runner",
                "imported_by_or_referenced_by": [],
                "scheduled_by": [],
                "registered_tool_name": None,
                "prepared_context_source": bool(gr.get("prepared_context_source")),
                "writes_state_guess": True,
                "external_side_effect_guess": True,
                "approval_required_guess": bool(gr.get("approval_required_for_tool_registry")),
                "status": "manual_only",
                "reasons": gnotes,
            }
        )

    tools_out: list[dict[str, Any]] = []
    for row in registry_rows:
        tn = str(row.get("tool_name") or "")
        rp = row.get("path")
        impl = ""
        exists = False
        if isinstance(rp, str):
            impl = rp.replace("\\", "/")
            if row.get("repo") == "ai-lab":
                cand = (ai_lab / impl).resolve()
                exists = cand.is_file()
            else:
                exists = False
        brain = brain_by_name.get(tn) or {}
        se = (brain.get("side_effects") or "").lower()
        read_only = se == "read_only"
        appr = bool(brain.get("approval_required"))
        meta_ok = bool(
            brain.get("description")
            and "risk_level" in brain
            and "side_effects" in brain
            and row.get("purpose")
            and row.get("inputs") is not None
        )
        tools_out.append(
            {
                "tool_name": tn,
                "source": "registry/scripts.json",
                "implementation_path": impl,
                "exists": exists,
                "action_type": "registry_script",
                "read_only": read_only,
                "approval_required": appr,
                "allowlist_eligible": read_only and not appr,
                "metadata_complete": meta_ok,
                "risks": [] if meta_ok else ["missing_or_partial_metadata"],
            }
        )

    reg_names = {str(r.get("tool_name")) for r in registry_rows}
    for t in brain_tools:
        tn = str(t.get("name") or "")
        if not tn or tn in reg_names:
            continue
        se = (t.get("side_effects") or "").lower()
        read_only = se == "read_only"
        appr = bool(t.get("approval_required"))
        meta_ok = all(
            k in t for k in ("description", "args", "side_effects", "approval_required", "risk_level")
        )
        tools_out.append(
            {
                "tool_name": tn,
                "source": "brain/tool_registry.py",
                "implementation_path": None,
                "exists": True,
                "action_type": "in_process_tool",
                "read_only": read_only,
                "approval_required": appr,
                "allowlist_eligible": read_only and not appr,
                "metadata_complete": meta_ok,
                "risks": [] if meta_ok else ["missing_or_partial_metadata"],
            },
        )

    for op in sorted(
        {
            "route_intent",
            "fetch_worker_repo_status",
        }
    ):
        tools_out.append(
            {
                "tool_name": f"supervisor_bridge:{op}",
                "source": "supervisor_bridge",
                "implementation_path": "command-center/command-center/backend/services/supervisor_bridge.py",
                "exists": (ai_lab / "command-center/command-center/backend/services/supervisor_bridge.py").is_file(),
                "action_type": "command_center_bridge",
                "read_only": op == "fetch_worker_repo_status",
                "approval_required": op != "fetch_worker_repo_status",
                "allowlist_eligible": op == "fetch_worker_repo_status",
                "metadata_complete": True,
                "risks": ["bridge_paths_require_governance_review"],
            }
        )

    tools_out.append(
        {
            "tool_name": "command_center:POST /api/tools/invoke",
            "source": "command_center_endpoint",
            "implementation_path": "command-center/command-center/backend/routers/tools.py",
            "exists": (ai_lab / "command-center/command-center/backend/routers/tools.py").is_file(),
            "action_type": "command_center_endpoint",
            "read_only": False,
            "approval_required": True,
            "allowlist_eligible": False,
            "metadata_complete": True,
            "risks": ["routes_supervisor_ops"],
        }
    )

    orphans: list[dict[str, Any]] = []
    for s in scripts_out:
        if s["status"] != "orphan_candidate":
            continue
        orphans.append(
            {
                "path": s["path"],
                "reason": "no_cross_refs_no_registry_no_ps1_chain",
                "recommended_action": "needs_review",
                "risk_level": "medium" if s.get("writes_state_guess") else "low",
            }
        )

    missing_meta = [t for t in tools_out if not t.get("metadata_complete")]
    write_guess_no_appr = [
        s
        for s in scripts_out
        if s.get("writes_state_guess") and not s.get("approval_required_guess") and s["classification"] == "cli_script"
    ]

    top_cleanup: list[str] = []
    for t in missing_meta[:10]:
        top_cleanup.append(f"tool:{t.get('tool_name')} -> complete metadata / align registry+brain")
    for s in write_guess_no_appr[:10]:
        top_cleanup.append(f"script:{s.get('path')} -> verify read-only or set approval path")

    missing_trig = [t for t in triggers if t.get("status") in ("missing_visibility", "assumption", "unknown")]

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso(),
        "ai_lab_root": str(ai_lab.resolve()),
        "total_scripts_scanned": len(scripts_out),
        "total_tools": len(tools_out),
        "total_triggers": len(triggers),
        "orphan_candidates": len(orphans),
        "deprecated_candidates": sum(
            1
            for s in scripts_out
            if s.get("classification") == "temp_probe"
            or "deprecated" in " ".join(s.get("reasons") or []).lower()
            or "_patch" in (s.get("path") or "").lower()
        ),
        "missing_metadata_tools": len(missing_meta),
        "write_capable_scripts_lacking_approval_guess": len(write_guess_no_appr),
        "growflow_inventory_scripts_merged": len(growflow_rows),
        "top_10_highest_priority_cleanup_items": top_cleanup[:10],
        "top_10_missing_triggers": [t.get("trigger_name", "") for t in missing_trig[:10]],
        "recommended_next_actions": [
            "Re-run after registry or scheduler changes",
            "Triage orphan_candidate rows before wiring",
            "Do not auto-register tools from this inventory",
        ],
    }

    (output_dir / "scripts.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "generated_at": summary["generated_at"], "scripts": scripts_out}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "tools.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "generated_at": summary["generated_at"], "tools": tools_out}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "triggers.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "generated_at": summary["generated_at"], "triggers": triggers}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "orphans.json").write_text(
        json.dumps({"schema_version": SCHEMA_VERSION, "generated_at": summary["generated_at"], "orphans": orphans}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Script / tool inventory (auto-generated)",
        "",
        f"Generated: `{summary['generated_at']}`",
        "",
        "## How to run",
        "",
        "```bash",
        "cd ai-lab",
        "python scripts/generate_integration_inventory.py",
        "```",
        "",
        "Optional:",
        "",
        "```bash",
        "python scripts/generate_integration_inventory.py --output-dir path/to/out --docs-path path/to/SCRIPT_TOOL_INVENTORY_AUTO.md",
        "```",
        "",
        "## Output files (machine-readable)",
        "",
        "| File | Role |",
        "|------|------|",
        "| `state/integration_inventory/scripts.json` | Every scanned script + Growflow merge |",
        "| `state/integration_inventory/tools.json` | Registry + brain tools + bridge/endpoint stubs |",
        "| `state/integration_inventory/triggers.json` | Lifespan loops + PowerShell wrappers |",
        "| `state/integration_inventory/orphans.json` | `orphan_candidate` scripts only |",
        "| `state/integration_inventory/summary.json` | Counts + top cleanup / trigger gaps |",
        "",
        "## Status values (scripts)",
        "",
        "- **wired** — clearly tied to app surface, registry, or builder role.",
        "- **partial** — referenced or scheduled via wrapper but not fully traced.",
        "- **manual_only** — diagnostics, probes, or Growflow host scripts.",
        "- **orphan_candidate** — no refs, registry, or PS1 chain (review before deleting).",
        "- **unknown_needs_review** — classifier could not bucket the path.",
        "",
        "## Orphan candidates",
        "",
        "Orphans are **not** failures. Treat `orphans.json` as a triage queue: confirm purpose,",
        "add references or registry entries if promoted, else **keep_manual_only**.",
        "",
        "## What not to auto-wire",
        "",
        "- Do not register tools from this JSON without human approval + metadata.",
        "- Do not treat `temp_probe` / `diagnostic` as production triggers.",
        "- Prepared context builders are infrastructure, not user tools.",
        "",
        "## Cadence",
        "",
        "- Run manually after major repo moves, new scripts, or registry edits.",
        "- Optional later: schedule weekly generation in CI or Task Scheduler (not enabled here).",
        "",
        "## Latest summary snapshot",
        "",
        f"- Total scripts: **{summary['total_scripts_scanned']}**",
        f"- Total tools: **{summary['total_tools']}**",
        f"- Triggers: **{summary['total_triggers']}**",
        f"- Orphan candidates: **{summary['orphan_candidates']}**",
        f"- Missing metadata tools: **{summary['missing_metadata_tools']}**",
        "",
        "## Scan scope (important)",
        "",
        "- Trees: `scripts/`, `brain/`, `command-center/.../backend/`, `command-center/.../frontend/src/`.",
        "- Directory names skipped: `__pycache__`, `node_modules`, `.venv`, `tests`, etc. (noise reduction).",
        "- `scripts.json` merges **Growflow** rows from `growflow_runners.json` when present (`../Growflow/...`).",
        "",
        "## `scripts.json` row fields",
        "",
        "| Field | Meaning |",
        "|-------|---------|",
        "| `classification` | Heuristic bucket (cli, diagnostic, backend, growflow merge, …). |",
        "| `writes_state_guess` / `approval_required_guess` | Regex heuristics — verify before trusting. |",
        "| `status` | `wired` / `partial` / `manual_only` / `orphan_candidate` / `unknown_needs_review`. |",
        "",
    ]
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("\n".join(md_lines), encoding="utf-8")

    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate integration inventory JSON + markdown.")
    p.add_argument("--output-dir", type=Path, default=None)
    p.add_argument("--docs-path", type=Path, default=None)
    args = p.parse_args(argv)
    root = _ai_lab_root()
    generate_integration_inventory(
        ai_lab=root,
        output_dir=args.output_dir,
        docs_path=args.docs_path,
    )
    print(f"wrote inventory under {(args.output_dir or root / 'state' / 'integration_inventory').resolve()}")
    print(f"wrote docs at {(args.docs_path or root / 'docs' / 'SCRIPT_TOOL_INVENTORY_AUTO.md').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
