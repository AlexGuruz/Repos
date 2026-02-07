from __future__ import annotations

import argparse
import os
import sys


def cmd_watcher_run(ns: argparse.Namespace) -> int:
    env = dict(os.environ)
    if ns.instance_id:
        env["KYLO_INSTANCE_ID"] = ns.instance_id
    if ns.years:
        env["KYLO_ACTIVE_YEARS"] = ns.years
    if ns.interval:
        env["KYLO_WATCH_INTERVAL_SECS"] = str(ns.interval)
    if ns.jitter is not None:
        env["KYLO_WATCH_JITTER_SECS"] = str(ns.jitter)
    if ns.config_path:
        env["KYLO_CONFIG_PATH"] = ns.config_path
    os.environ.update(env)

    from kylo.watcher_runtime import main as watcher_main

    argv: list[str] = []
    if ns.years:
        argv += ["--years", ns.years]
    if ns.instance_id:
        argv += ["--instance-id", ns.instance_id]
    return int(watcher_main(argv))


def cmd_hub(ns: argparse.Namespace) -> int:
    env = dict(os.environ)
    if ns.config_path:
        env["KYLO_CONFIG_PATH"] = ns.config_path
    os.environ.update(env)

    from kylo.hub import main as hub_main

    argv: list[str] = []
    if ns.hub_cmd == "start":
        argv += ["start"]
        if ns.all:
            argv += ["--all"]
        if ns.instance_id:
            argv += ["--instance", ns.instance_id]
        if ns.registry:
            argv += ["--registry", ns.registry]
    elif ns.hub_cmd == "stop":
        argv += ["stop"]
        if ns.all:
            argv += ["--all"]
        if ns.instance_id:
            argv += ["--instance", ns.instance_id]
    elif ns.hub_cmd == "status":
        argv += ["status"]
    else:
        raise SystemExit("Unknown hub command")

    return int(hub_main(argv))


def cmd_ops_dashboard(ns: argparse.Namespace) -> int:
    from pathlib import Path

    from services.ops.dashboard import write_dashboard_json

    out = Path(ns.out) if ns.out else None
    write_dashboard_json(out)
    return 0


def cmd_config_validate(ns: argparse.Namespace) -> int:
    from kylo.config_validate import main as validate_main

    argv: list[str] = []
    if ns.path:
        argv += ["--path", ns.path]
    if ns.pretty:
        argv += ["--pretty"]
    return int(validate_main(argv))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kylo", description="Kylo CLI")
    sub = p.add_subparsers(dest="top", required=True)

    # watcher
    w = sub.add_parser("watcher", help="Watcher commands")
    wsub = w.add_subparsers(dest="watcher_cmd", required=True)
    wr = wsub.add_parser("run", help="Run a watcher instance")
    wr.add_argument("--instance-id", required=False, help="Instance id (recommended)")
    wr.add_argument("--years", required=False, help="Comma-separated years to watch")
    wr.add_argument("--interval", type=int, default=None, help="Watch interval seconds")
    wr.add_argument("--jitter", type=int, default=None, help="Watch jitter seconds")
    wr.add_argument("--config-path", default=None, help="Config path (e.g., config/global.yaml)")
    wr.set_defaults(func=cmd_watcher_run)

    # hub
    h = sub.add_parser("hub", help="Supervisor hub commands")
    hsub = h.add_subparsers(dest="hub_cmd", required=True)

    hs = hsub.add_parser("start", help="Start hub supervisor (foreground)")
    hs.add_argument("--all", action="store_true", help="Start all enabled instances")
    hs.add_argument("--instance-id", default=None, help="Start a single instance")
    hs.add_argument("--registry", default=None, help="Registry path (default: config/instances/index.yaml)")
    hs.add_argument("--config-path", default=None, help="Config path (e.g., config/global.yaml)")
    hs.set_defaults(func=cmd_hub)

    hst = hsub.add_parser("status", help="Show hub status")
    hst.add_argument("--config-path", default=None, help="Config path (optional)")
    hst.set_defaults(func=cmd_hub)

    hp = hsub.add_parser("stop", help="Stop hub-managed instances")
    hp.add_argument("--all", action="store_true", help="Stop all instances")
    hp.add_argument("--instance-id", default=None, help="Stop a single instance")
    hp.add_argument("--config-path", default=None, help="Config path (optional)")
    hp.set_defaults(func=cmd_hub)

    # ops
    ops = sub.add_parser("ops", help="Operational tools")
    opssub = ops.add_subparsers(dest="ops_cmd", required=True)
    od = opssub.add_parser("dashboard", help="Build local ops dashboard JSON")
    od.add_argument("--out", default=None, help="Output path (default: .kylo/ops/dashboard.json)")
    od.set_defaults(func=cmd_ops_dashboard)

    # config
    cfg = sub.add_parser("config", help="Config tools")
    cfgsub = cfg.add_subparsers(dest="config_cmd", required=True)
    cv = cfgsub.add_parser("validate", help="Validate config")
    cv.add_argument("--path", default=None, help="Config file path (defaults to config/kylo.config.yaml)")
    cv.add_argument("--pretty", action="store_true", help="Pretty print normalized JSON")
    cv.set_defaults(func=cmd_config_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return int(ns.func(ns))

