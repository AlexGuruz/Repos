from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from services.common.config_loader import load_config
from services.common.instance import (
    default_posting_state_path,
    default_watch_state_path,
    get_instance_id,
    get_watcher_name,
    legacy_posting_state_path,
    legacy_watch_state_path,
    migrate_legacy_file,
)
from services.intake.csv_downloader import download_petty_cash_csv
from services.ops.heartbeat import Heartbeat, write_heartbeat
from services.rules.jgdtruth_provider import fetch_rules_from_jgdtruth
from services.sheets.poster import _extract_spreadsheet_id

#
# IMPORTANT:
# - The watcher maintains a lightweight checksum state (rules + intake) to decide
#   whether to trigger a posting run.
# - The incremental posting system maintains its own state (cell signatures, etc.)
#   in `services/state/store.py`.
#
# These two state files MUST NOT share the same path.
#
WATCH_STATE_PATH = os.environ.get("KYLO_WATCH_STATE_PATH", os.path.join(".kylo", "watch_state.json"))


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _load_state() -> Dict[str, Any]:
    try:
        if os.path.exists(WATCH_STATE_PATH):
            with open(WATCH_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(WATCH_STATE_PATH), exist_ok=True)
    with open(WATCH_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _run_sync_hook() -> bool:
    """Run sync runner once before each watcher tick when enabled."""
    if os.environ.get("KYLO_SYNC_BEFORE_TICK", "").strip().lower() not in ("1", "true", "yes", "y"):
        return True
    repo_root = Path(__file__).resolve().parents[1]
    sync_path = repo_root / "tools" / "scripthub_legacy" / "sync_runner.py"
    if not sync_path.exists():
        print(f"[sync-hook] Missing sync runner at {sync_path}")
        return False
    cmd = [sys.executable, "-u", str(sync_path), "--once"]
    years = (os.environ.get("KYLO_ACTIVE_YEARS") or "").strip()
    if years:
        cmd.extend(["--years", years])
    print(f"[sync-hook] Running: {' '.join(cmd)}")
    try:
        rc = subprocess.call(cmd, cwd=str(repo_root))
        if rc != 0:
            print(f"[sync-hook] Failed with exit code {rc}")
            return False
    except Exception as e:
        print(f"[sync-hook] Exception: {e}")
        return False
    return True


def rules_checksum(company: str) -> str:
    rules = fetch_rules_from_jgdtruth(company)
    approved = [(r.source or "", r.target_sheet or "", r.target_header or "") for r in rules.values() if r.approved]
    approved.sort()
    payload = "\n".join(["|".join(t) for t in approved])
    return _md5(payload)


def _active_years(cfg) -> List[int] | None:
    """Return active years filter for year_workbooks, or None for 'no filtering'."""
    raw = (os.environ.get("KYLO_ACTIVE_YEARS") or "").strip()
    if raw:
        years: List[int] = []
        for part in re.split(r"[,\s]+", raw):
            if not part:
                continue
            if str(part).strip().isdigit():
                years.append(int(part))
        return years or None

    cfg_val = cfg.get("year_workbooks_active")
    if isinstance(cfg_val, list) and cfg_val:
        years = []
        for it in cfg_val:
            try:
                years.append(int(str(it).strip()))
            except Exception:
                continue
        return years or None

    ym = cfg.get("year_workbooks") or {}
    if isinstance(ym, dict) and ym:
        years = []
        for k in ym.keys():
            try:
                years.append(int(str(k).strip()))
            except Exception:
                continue
        return years or None
    return None


def intake_checksum(cfg, company: str) -> str:
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == company), None)
    if not comp:
        return ""
    sa = cfg.get("google.service_account_json_path") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    parts: List[str] = []

    # If year_workbooks intake routing is configured, include ONLY active years (if set).
    # This ensures each watcher instance (KYLO_2025, KYLO_2026) reads transactions from its correct year workbook.
    # KYLO_2025 watcher: active_years = {2025} → reads from year_workbooks.2025.intake_workbook_url
    # KYLO_2026 watcher: active_years = {2026} → reads from year_workbooks.2026.intake_workbook_url
    intake_urls: List[str] = []
    try:
        active = _active_years(cfg)
        ym = cfg.get("year_workbooks") or {}
        if isinstance(ym, dict):
            for y, spec in ym.items():
                try:
                    yi = int(str(y).strip())
                except Exception:
                    continue
                if active and yi not in active:
                    continue
                if isinstance(spec, dict):
                    u = spec.get("intake_workbook_url")
                else:
                    u = cfg.get(f"year_workbooks.{yi}.intake_workbook_url")
                if u and str(u).strip():
                    intake_urls.append(str(u).strip())
    except Exception:
        intake_urls = []
    if not intake_urls:
        intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
        intake_urls = [str(intake_url)]

    intake_sids = []
    for u in intake_urls:
        try:
            sid = _extract_spreadsheet_id(str(u))
            if sid and sid not in intake_sids:
                intake_sids.append(sid)
        except Exception:
            continue

    extra_tabs: List[str] = []
    try:
        extra_tabs = [str(t) for t in (cfg.get("intake.extra_tabs") or []) if str(t).strip()]
    except Exception:
        extra_tabs = []

    for sid in intake_sids:
        for tab in tuple(["TRANSACTIONS", "BANK"]) + tuple(extra_tabs):
            try:
                csv_content = download_petty_cash_csv(sid, sa, sheet_name_override=tab)
                parts.append(_md5(csv_content))
            except Exception:
                parts.append("-")
    return _md5("|".join(parts))


def tick_once(companies: List[str]) -> Dict[str, Any]:
    cfg = load_config()
    state = _load_state()
    # state schema (v2+):
    # - seen.{cid}.rules/intake: latest observed checksums
    # - acked.{cid}.rules/intake: last successfully posted checksums
    if "seen" not in state and ("rules" in state or "intake" in state):
        # Migrate legacy state keys
        legacy_rules = state.get("rules", {}) or {}
        legacy_intake = state.get("intake", {}) or {}
        state["seen"] = {
            cid: {"rules": legacy_rules.get(cid), "intake": legacy_intake.get(cid)}
            for cid in set(list(legacy_rules.keys()) + list(legacy_intake.keys()))
        }
        state["acked"] = {
            cid: {"rules": legacy_rules.get(cid), "intake": legacy_intake.get(cid)}
            for cid in set(list(legacy_rules.keys()) + list(legacy_intake.keys()))
        }
        state.pop("rules", None)
        state.pop("intake", None)

    changed: Dict[str, Any] = {}
    rules_changed_companies: List[str] = []
    for cid in companies:
        try:
            rsum = rules_checksum(cid)
        except Exception:
            rsum = ""
        try:
            tsum = intake_checksum(cfg, cid)
        except Exception:
            tsum = ""
        seen_prev = (state.get("seen", {}) or {}).get(cid, {}) if isinstance(state.get("seen", {}), dict) else {}
        ack_prev = (state.get("acked", {}) or {}).get(cid, {}) if isinstance(state.get("acked", {}), dict) else {}

        # Always update "seen" so we don't re-process the same change repeatedly.
        state.setdefault("seen", {})
        state["seen"][cid] = {"rules": rsum, "intake": tsum}

        # Posting should be driven by "acked" (last success), so enabling posting later still catches up.
        prev_rules = ack_prev.get("rules")
        prev_intake = ack_prev.get("intake")
        if prev_rules != rsum or prev_intake != tsum:
            changed[cid] = {
                "rules": rsum,
                "intake": tsum,
                "seen_changed": (seen_prev.get("rules") != rsum or seen_prev.get("intake") != tsum),
            }
            if prev_rules != rsum:
                rules_changed_companies.append(cid)

    # Safe mode / kill switches (env vars)
    read_only = os.environ.get("KYLO_READ_ONLY", "").strip().lower() in ("1", "true", "yes", "y")
    disable_instances_raw = (os.environ.get("KYLO_DISABLE_POSTING_FOR", "") or "").strip()
    disable_companies_raw = (os.environ.get("KYLO_DISABLE_POSTING_COMPANIES", "") or "").strip()
    instance_id = (os.environ.get("KYLO_INSTANCE_ID", "") or "").strip()
    company_key = instance_id.split(":", 1)[0].split("_", 1)[0].strip().upper() if instance_id else ""
    disabled = False
    disabled_reason = None
    if instance_id and disable_instances_raw:
        disabled_instances = {p.strip() for p in re.split(r"[,\s]+", disable_instances_raw) if p.strip()}
        if instance_id in disabled_instances:
            disabled = True
            disabled_reason = f"disabled_instance:{instance_id}"
    if (not disabled) and company_key and disable_companies_raw:
        disabled_companies = {p.strip().upper() for p in re.split(r"[,\s]+", disable_companies_raw) if p.strip()}
        if company_key in disabled_companies:
            disabled = True
            disabled_reason = f"disabled_company:{company_key}"

    # Circuit breaker (per instance): track consecutive failures and pause posting.
    cb = cfg.get("runtime.circuit_breaker") or {}
    try:
        cb_max = int((cb.get("max_consecutive_failures") if isinstance(cb, dict) else None) or 5)
    except Exception:
        cb_max = 5
    try:
        cb_pause_min = int((cb.get("pause_minutes") if isinstance(cb, dict) else None) or 30)
    except Exception:
        cb_pause_min = 30

    cb_state = state.get("circuit_breaker") or {}
    if not isinstance(cb_state, dict):
        cb_state = {}
    paused_until = str(cb_state.get("paused_until") or "").strip()
    consecutive_failures = int(cb_state.get("consecutive_failures") or 0) if str(cb_state.get("consecutive_failures") or "0").isdigit() else 0

    now_ts = time.time()
    paused_active = False
    if paused_until:
        try:
            pu = float(paused_until)
            if pu > now_ts:
                paused_active = True
        except Exception:
            paused_active = False

    change_detected = bool(changed)
    should_post = change_detected and (not read_only) and (not disabled) and (not paused_active)
    posting_attempted = bool(should_post)
    posting_skipped_reason: str | None = None
    if not change_detected:
        posting_skipped_reason = "no_changes"
    elif read_only:
        posting_skipped_reason = "read_only"
    elif disabled:
        posting_skipped_reason = disabled_reason or "disabled"
    elif paused_active:
        posting_skipped_reason = "circuit_breaker_paused"

    summaries: Dict[str, Any] = {}
    if should_post:
        from services.posting.jgdtruth_poster import run as post_run
        from services.state.store import StateError, load_state as load_posting_state, save_state as save_posting_state

        for cid in changed.keys():
            try:
                rules_changed = cid in rules_changed_companies
                if rules_changed:
                    try:
                        posting_state = load_posting_state()
                        posting_state.cell_signatures.pop(cid, None)
                        posting_state.clear_skipped(cid)
                        save_posting_state(posting_state)
                        print(f"[RULE CHANGE] Cleared state for {cid} to force re-processing")
                    except StateError as e:
                        print(f"[WARN] Could not clear posting state for {cid}: {e}")
                summaries[cid] = post_run(cid, rules_changed=rules_changed) or {}
            except Exception as e:
                print(f"[ERROR] Failed to process {cid}: {e}")
                summaries[cid] = {"error": True}

        any_error = any(isinstance(s, dict) and s.get("error") for s in summaries.values())
        if any_error:
            consecutive_failures = consecutive_failures + 1
            if consecutive_failures >= cb_max:
                paused_until_epoch = now_ts + (cb_pause_min * 60)
                state["circuit_breaker"] = {"paused_until": str(paused_until_epoch), "consecutive_failures": consecutive_failures}
                print(f"[CIRCUIT] Pausing posting for {cb_pause_min} minutes after {consecutive_failures} failures")
            else:
                state["circuit_breaker"] = {"paused_until": "", "consecutive_failures": consecutive_failures}
        else:
            consecutive_failures = 0
            state["circuit_breaker"] = {"paused_until": "", "consecutive_failures": 0}
            state.setdefault("acked", {})
            for cid, sums in changed.items():
                state["acked"][cid] = {"rules": sums.get("rules"), "intake": sums.get("intake")}

        _save_state(state)
    else:
        state["circuit_breaker"] = {"paused_until": paused_until, "consecutive_failures": consecutive_failures}
        _save_state(state)

    return {
        "changed": changed,
        "summaries": summaries,
        "change_detected": change_detected,
        "posting_attempted": posting_attempted,
        "posting_skipped_reason": posting_skipped_reason,
        "read_only": read_only,
        "posting_disabled": disabled,
        "posting_disabled_reason": disabled_reason,
        "circuit_breaker_paused_until": paused_until if paused_active else "",
        "circuit_breaker_consecutive_failures": consecutive_failures,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kylo watcher (rules+intake checksums -> posting)")
    ap.add_argument(
        "--years",
        default=None,
        help="Comma-separated years to watch (overrides KYLO_ACTIVE_YEARS and config year_workbooks_active)",
    )
    ap.add_argument(
        "--instance-id",
        default=None,
        help="Instance identifier for isolation (sets KYLO_INSTANCE_ID and per-instance defaults)",
    )
    ap.add_argument(
        "--once",
        action="store_true",
        help="Run a single tick then exit (useful for benchmarks/smoke tests)",
    )
    args = ap.parse_args(argv)
    if args.years:
        os.environ["KYLO_ACTIVE_YEARS"] = str(args.years)
    if args.instance_id:
        os.environ["KYLO_INSTANCE_ID"] = str(args.instance_id).strip()

    global WATCH_STATE_PATH
    if "KYLO_WATCH_STATE_PATH" not in os.environ:
        # Ensure we get the instance ID from environment (it should be set by the start script)
        iid = get_instance_id()
        if not iid:
            # Fallback: try to get from environment again
            iid = (os.environ.get("KYLO_INSTANCE_ID") or "").strip() or None
        if iid:
            new_path = default_watch_state_path(iid)
            migrate_legacy_file(legacy_path=legacy_watch_state_path(iid), new_path=new_path)
            # Also migrate any old watch_state_<year>.json files
            legacy_year_path = Path(".kylo") / f"watch_state_{iid.split('_')[-1]}.json"
            if legacy_year_path.exists() and legacy_year_path != legacy_watch_state_path(iid):
                migrate_legacy_file(legacy_path=legacy_year_path, new_path=new_path)
            WATCH_STATE_PATH = str(new_path)
            # Also migrate any legacy post_state files
            legacy_post_path = legacy_posting_state_path(iid)
            new_post_path = default_posting_state_path(iid)
            migrate_legacy_file(legacy_path=legacy_post_path, new_path=new_post_path)
            # Also migrate any old post_state_<year>.json files
            legacy_year_post_path = Path(".kylo") / f"post_state_{iid.split('_')[-1]}.json"
            if legacy_year_post_path.exists() and legacy_year_post_path != legacy_post_path:
                migrate_legacy_file(legacy_path=legacy_year_post_path, new_path=new_post_path)

    cfg = load_config()
    companies_cfg = cfg.get("sheets.companies") or []
    companies = [str(it.get("key")).strip().upper() for it in companies_cfg]
    # Enforce single-company per instance when instance id is present.
    try:
        iid = (os.environ.get("KYLO_INSTANCE_ID") or "").strip()
        if iid:
            company_key = iid.split(":", 1)[0].split("_", 1)[0].strip().upper()
            if company_key:
                if company_key in companies:
                    companies = [company_key]
                else:
                    print(
                        f"[WATCH] WARN: instance company '{company_key}' not found in config.sheets.companies; keeping configured companies={companies}"
                    )
    except Exception:
        pass

    interval = int(os.environ.get("KYLO_WATCH_INTERVAL_SECS", str(cfg.get("runtime.watch_interval_secs", 300))))
    jitter = int(os.environ.get("KYLO_WATCH_JITTER_SECS", str(cfg.get("runtime.watch_jitter_secs", 15))))

    try:
        instance_id = get_instance_id()
        if not instance_id:
            # Ensure instance_id is set from environment
            instance_id = (os.environ.get("KYLO_INSTANCE_ID") or "").strip() or None
        watcher_name = get_watcher_name()
        active_env = (os.environ.get("KYLO_ACTIVE_YEARS") or "").strip()
        active_cfg = cfg.get("year_workbooks_active")
        active_effective = _active_years(cfg)
        post_apply = bool(cfg.get("posting.sheets.apply", False))
        if os.environ.get("KYLO_STATE_PATH"):
            post_state_path = os.environ.get("KYLO_STATE_PATH", ".kylo/state.json")
        elif instance_id:
            post_state_path = str(default_posting_state_path(instance_id))
            # Ensure directory exists
            os.makedirs(os.path.dirname(post_state_path), exist_ok=True)
        else:
            post_state_path = ".kylo/state.json"
        if watcher_name:
            print(f"[WATCH] name={watcher_name}")
        if instance_id:
            print(f"[WATCH] instance_id={instance_id}")
        print(f"[WATCH] watch_state={WATCH_STATE_PATH}")
        print(f"[WATCH] posting_state={post_state_path}")
        print(f"[WATCH] posting.sheets.apply={post_apply}")
        print(f"[WATCH] active_years env='{active_env or '<unset>'}' cfg={active_cfg} effective={active_effective}")
    except Exception:
        pass

    try:
        _save_state(_load_state())
    except Exception:
        pass
    try:
        from services.state.store import load_state as _load_post_state
        from services.state.store import save_state as _save_post_state

        st = _load_post_state()
        _save_post_state(st)
    except Exception:
        pass

    try:
        random.seed((get_instance_id() or get_watcher_name() or "kylo") + "|" + str(time.time()))
    except Exception:
        pass

    print(f"Watching companies {companies} every {interval}s (+/-{jitter}s jitter) for rule/tx changes...")

    hb = None
    try:
        # Ensure instance ID is properly set from environment
        iid = get_instance_id()
        if not iid:
            iid = (os.environ.get("KYLO_INSTANCE_ID") or "").strip() or None
        if not iid:
            iid = (get_watcher_name() or "kylo").strip()
        if os.environ.get("KYLO_STATE_PATH"):
            post_state_path = os.environ.get("KYLO_STATE_PATH", ".kylo/state.json")
        elif iid:
            post_state_path = str(default_posting_state_path(iid))
            # Ensure directory exists
            os.makedirs(os.path.dirname(post_state_path), exist_ok=True)
        else:
            post_state_path = ".kylo/state.json"
        hb = Heartbeat(
            instance_id=iid,
            company_key=iid.split("_", 1)[0].split(":", 1)[0].strip().upper() if iid else "",
            active_years=_active_years(cfg),
            watch_state_path=str(WATCH_STATE_PATH),
            posting_state_path=post_state_path,
            watch_interval_secs=int(interval),
        )
    except Exception:
        hb = None

    while True:
        try:
            tick_start = time.time()
            if not _run_sync_hook():
                time.sleep(5)
                continue
            if hb is not None:
                try:
                    hb.last_tick_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    hb.last_tick_duration_ms = None
                    hb.last_error = None
                    hb.last_error_at = None
                    hb.last_post_started_at = None
                    hb.last_post_finished_at = None
                    hb.last_post_ok = None
                    hb.last_post_summary = None
                    write_heartbeat(hb)
                except Exception:
                    pass

            res = tick_once(companies)
            changed = res.get("changed") or {}
            summaries = res.get("summaries") or {}
            tick_end = time.time()
            tick_ms = int(max(0.0, (tick_end - tick_start) * 1000.0))

            if hb is not None:
                try:
                    hb.read_only = bool(res.get("read_only", False))
                    hb.posting_disabled = bool(res.get("posting_disabled", False))
                    hb.posting_disabled_reason = res.get("posting_disabled_reason")
                    hb.circuit_breaker_paused_until = res.get("circuit_breaker_paused_until") or None
                    hb.circuit_breaker_consecutive_failures = int(res.get("circuit_breaker_consecutive_failures", 0) or 0)
                    hb.change_detected = bool(res.get("change_detected", False))
                    hb.posting_attempted = bool(res.get("posting_attempted", False))
                    hb.posting_skipped_reason = res.get("posting_skipped_reason")
                    if changed:
                        hb.last_change_detected_at = hb.last_tick_at
                        hb.last_post_started_at = hb.last_tick_at
                        hb.last_post_finished_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

                        ok = True
                        total_cells = 0
                        total_rows = 0
                        skipped_no_rule = 0
                        skipped_header_or_date = 0
                        if isinstance(summaries, dict):
                            for _cid, s in summaries.items():
                                if not isinstance(s, dict):
                                    continue
                                if s.get("error"):
                                    ok = False
                                total_cells += int(s.get("cells_written", 0) or 0)
                                total_rows += int(s.get("rows_marked_true", 0) or 0)
                                skipped_no_rule += int(s.get("skipped_no_rule", 0) or 0)
                                skipped_header_or_date += int(s.get("skipped_header_or_date", 0) or 0)

                        hb.last_post_ok = ok
                        hb.last_post_summary = {
                            "cells_written": total_cells,
                            "rows_marked_true": total_rows,
                            "skipped_no_rule": skipped_no_rule,
                            "skipped_header_or_date": skipped_header_or_date,
                        }
                    else:
                        hb.last_post_summary = None
                        hb.last_post_ok = None
                    hb.last_tick_duration_ms = tick_ms
                    hb.last_error = None
                    hb.last_error_at = None
                    write_heartbeat(hb)
                except Exception:
                    pass

            if bool(res.get("posting_attempted", False)) and changed:
                print(f"Posted for: {list(changed.keys())}")
                for cid, s in summaries.items():
                    if isinstance(s, dict) and s:
                        cw = s.get("cells_written", 0)
                        rm = s.get("rows_marked_true", 0)
                        tabs = s.get("tabs", [])
                        print(f"{cid}: cells_written={cw}, rows_marked_true={rm}, tabs={tabs}")
        except Exception as e:
            if hb is not None:
                try:
                    hb.last_tick_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                    hb.last_tick_duration_ms = None
                    hb.last_post_ok = False
                    hb.last_error = str(e)
                    hb.last_error_at = hb.last_tick_at
                    write_heartbeat(hb)
                except Exception:
                    pass

        if bool(getattr(args, "once", False)):
            return 0

        base = max(60, int(interval))
        j = max(0, int(jitter))
        sleep_s = float(base)
        if j > 0:
            sleep_s = max(60.0, base + random.uniform(-j, j))
        time.sleep(sleep_s)


if __name__ == "__main__":
    raise SystemExit(main())

