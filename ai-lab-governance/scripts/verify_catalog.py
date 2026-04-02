#!/usr/bin/env python3
"""
Validate registry/components.yaml and registry/environments.yaml against JSON Schema,
referential integrity, capability vs lifecycle roll-up, and built/evidence invariants.

Exit codes: 0 = pass, 1 = validation errors, 2 = usage/config errors

Environment:
  AI_LAB_GOVERNANCE_ROOT — repo root (default: parent of scripts/)
  CATALOG_STRICT=1       — fail if lifecycle_state: built without passing fresh evidence;
                           fail invalid lifecycle_override (built vs capabilities)
  CATALOG_EVIDENCE_MAX_AGE_HOURS — freshness for observed_at (default: 168)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML required. pip install -r scripts/requirements-catalog.txt", file=sys.stderr)
    sys.exit(2)

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    print("FAIL: jsonschema required. pip install -r scripts/requirements-catalog.txt", file=sys.stderr)
    sys.exit(2)


def _root() -> Path:
    r = os.environ.get("AI_LAB_GOVERNANCE_ROOT")
    if r:
        return Path(r)
    return Path(__file__).resolve().parent.parent


def _load_json_schema(name: str) -> dict[str, Any]:
    p = _root() / "schemas" / name
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_iso_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _validate_component_caps_vs_lifecycle(comp: dict[str, Any], strict: bool) -> list[str]:
    errors: list[str] = []
    state = comp.get("lifecycle_state")
    caps = comp.get("capabilities") or {}
    override = comp.get("lifecycle_override_reason")
    cid = comp.get("id", "?")

    non_na = {k: v for k, v in caps.items() if v != "na"}
    has_incomplete = any(v in ("unbuilt", "partial") for v in non_na.values())

    if state == "built" and has_incomplete:
        if not override or not str(override).strip():
            errors.append(
                f"component {cid}: lifecycle_state built but capabilities have "
                f"partial/unbuilt; set lifecycle_override_reason or fix capabilities"
            )

    if override and str(override).strip():
        print(f"WARNING: component {cid} has lifecycle_override_reason set — requires approval_owner review per plan.", file=sys.stderr)

    return errors


def _validate_built_evidence(comp: dict[str, Any], strict: bool, max_age_h: float) -> list[str]:
    errors: list[str] = []
    if comp.get("lifecycle_state") != "built":
        return errors
    cid = comp.get("id", "?")
    evidence = comp.get("evidence") or {}
    now = datetime.now(timezone.utc)
    for key, ev in evidence.items():
        if not ev.get("required_for_lifecycle"):
            continue
        st = ev.get("status")
        if st != "pass":
            errors.append(
                f"component {cid} built: evidence {key!r} must be status pass (got {st!r})"
            )
            continue
        obs_raw = ev.get("observed_at")
        obs = _parse_iso_utc(obs_raw) if obs_raw else None
        if obs is None:
            errors.append(f"component {cid} built: evidence {key!r} needs valid observed_at")
            continue
        age_h = (now - obs).total_seconds() / 3600.0
        if age_h > max_age_h:
            errors.append(
                f"component {cid} built: evidence {key!r} stale ({age_h:.1f}h > {max_age_h}h)"
            )
    return errors


def main() -> int:
    root = _root()
    strict = os.environ.get("CATALOG_STRICT", "").strip() in ("1", "true", "yes")
    try:
        max_age_h = float(os.environ.get("CATALOG_EVIDENCE_MAX_AGE_HOURS", "168"))
    except ValueError:
        print("FAIL: CATALOG_EVIDENCE_MAX_AGE_HOURS must be numeric", file=sys.stderr)
        return 2

    comp_path = root / "registry" / "components.yaml"
    env_path = root / "registry" / "environments.yaml"
    reg_path = root / "registry" / "repo_registry.json"

    for p in (comp_path, env_path, reg_path):
        if not p.is_file():
            print(f"FAIL: missing {p.relative_to(root)}", file=sys.stderr)
            return 1

    with comp_path.open(encoding="utf-8") as f:
        comp_doc = yaml.safe_load(f)
    with env_path.open(encoding="utf-8") as f:
        env_doc = yaml.safe_load(f)
    with reg_path.open(encoding="utf-8") as f:
        reg_doc = json.load(f)

    if not isinstance(comp_doc, dict) or "components" not in comp_doc:
        print("FAIL: components.yaml must be a mapping with 'components' array", file=sys.stderr)
        return 1
    if not isinstance(env_doc, dict) or "environments" not in env_doc:
        print("FAIL: environments.yaml must be a mapping with 'environments' array", file=sys.stderr)
        return 1

    components: list[dict[str, Any]] = comp_doc["components"]
    environments: list[dict[str, Any]] = env_doc["environments"]
    repos = reg_doc.get("repos") or []
    repo_ids = {r["repo_id"] for r in repos if isinstance(r, dict) and "repo_id" in r}

    env_ids = {e["id"] for e in environments if isinstance(e, dict) and "id" in e}

    schema_dir = root / "schemas"
    comp_schema = _load_json_schema("component.schema.json")
    env_schema = _load_json_schema("environment.schema.json")

    comp_validator = Draft7Validator(comp_schema)
    env_validator = Draft7Validator(env_schema)

    errors: list[str] = []
    seen_ids: set[str] = set()

    for comp in components:
        if not isinstance(comp, dict):
            errors.append("each component must be a mapping")
            continue
        cid = comp.get("id")
        if cid in seen_ids:
            errors.append(f"duplicate component id: {cid}")
        seen_ids.add(str(cid))
        for err in comp_validator.iter_errors(comp):
            errors.append(f"component {cid}: {err.message} at {'/'.join(str(p) for p in err.path)}")

        pr = comp.get("primary_repo")
        if pr and pr not in repo_ids:
            errors.append(f"component {cid}: unknown primary_repo {pr!r} (not in repo_registry.json)")

        for rr in comp.get("related_repos") or []:
            if rr not in repo_ids:
                errors.append(f"component {cid}: unknown related_repos entry {rr!r}")

        for env_key in (comp.get("environments") or {}).keys():
            if env_key not in env_ids:
                errors.append(f"component {cid}: environments key {env_key!r} not defined in environments.yaml")

        errors.extend(_validate_component_caps_vs_lifecycle(comp, strict))
        if strict:
            errors.extend(_validate_built_evidence(comp, strict, max_age_h))

    for env in environments:
        if not isinstance(env, dict):
            errors.append("each environment must be a mapping")
            continue
        eid = env.get("id")
        for err in env_validator.iter_errors(env):
            errors.append(f"environment {eid}: {err.message} at {'/'.join(str(p) for p in err.path)}")

    if errors:
        for e in errors:
            print("FAIL:", e, file=sys.stderr)
        return 1

    print("OK: catalog verification passed (strict=%s)" % strict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
