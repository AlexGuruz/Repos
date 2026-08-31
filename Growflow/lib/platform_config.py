"""
Growflow Ops Platform config — path injection, org_id, API bind, SLO thresholds.

No hard-coded E:\\Repos outside discovery helpers. Override via env or YAML.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORG_ID = "nugz"
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "platform.yaml"


@dataclass
class GrowflowPlatformConfig:
    org_id: str = DEFAULT_ORG_ID
    timezone: str = "America/Chicago"
    repo_root: Path = field(default_factory=lambda: REPO_ROOT)
    data_dir: Path = field(default_factory=lambda: REPO_ROOT / "data")
    facts_db: Path = field(default_factory=lambda: REPO_ROOT / "data" / "growflow_facts.db")
    cache_db: Path = field(default_factory=lambda: REPO_ROOT / "data" / "retail_dashboard.db")
    retail_dashboard_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "retail_dashboard_latest.json"
    )
    capital_json: Path = field(default_factory=lambda: REPO_ROOT / "data" / "retail_capital_latest.json")
    consignment_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "retail_consignment_latest.json"
    )
    reconciliation_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "retail_reconciliation_latest.json"
    )
    platform_status_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "platform_status_latest.json"
    )
    sales_projection_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "sales_projection_latest.json"
    )
    company_bi_json: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "company_bi_report_latest.json"
    )
    transfer_db: Path = field(default_factory=lambda: REPO_ROOT / "data" / "transfer_receipts.db")
    consignment_db: Path = field(default_factory=lambda: REPO_ROOT / "data" / "consignment.db")
    layer2_csv: Path = field(
        default_factory=lambda: REPO_ROOT / "data" / "projection_by_category_brand_layer2_recovery.csv"
    )
    sheets_transactions_db: Path = field(
        default_factory=lambda: REPO_ROOT / "company_bi" / "db" / "sheets_transactions.db"
    )
    api_host: str = "127.0.0.1"
    api_port: int = 8791
    retail_slo_seconds: int = 4 * 3600
    consignment_slo_seconds: int = 24 * 3600
    capital_slo_seconds: int = 48 * 3600
    projection_slo_seconds: int = 12 * 3600
    fixture_order_count_max: int = 3
    fixture_net_sales_max: float = 100.0


def _resolve(root: Path, raw: str | Path | None, default: Path) -> Path:
    if raw is None or str(raw).strip() == "":
        return default
    p = Path(raw)
    return p if p.is_absolute() else (root / p)


def load_platform_config(path: Path | str | None = None) -> GrowflowPlatformConfig:
    root = REPO_ROOT
    env_root = os.environ.get("GROWFLOW_REPO_ROOT", "").strip()
    if env_root:
        root = Path(env_root).expanduser().resolve()

    cfg_path = Path(path) if path else Path(
        os.environ.get("GROWFLOW_PLATFORM_CONFIG", str(root / "config" / "platform.yaml"))
    )
    raw: dict[str, Any] = {}
    if cfg_path.is_file():
        loaded = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            raw = loaded

    org_id = (
        os.environ.get("GROWFLOW_ORG_ID", "").strip()
        or str(raw.get("org_id") or DEFAULT_ORG_ID)
    )
    data_dir = _resolve(root, raw.get("data_dir") or os.environ.get("GROWFLOW_DATA_DIR"), root / "data")
    paths = raw.get("paths") if isinstance(raw.get("paths"), dict) else {}
    api = raw.get("api") if isinstance(raw.get("api"), dict) else {}
    slo = raw.get("slo") if isinstance(raw.get("slo"), dict) else {}
    fixture = raw.get("fixture_detector") if isinstance(raw.get("fixture_detector"), dict) else {}

    def pget(key: str, default_name: str) -> Path:
        return _resolve(root, paths.get(key) or os.environ.get(f"GROWFLOW_{key.upper()}"), data_dir / default_name)

    return GrowflowPlatformConfig(
        org_id=org_id,
        timezone=str(raw.get("timezone") or os.environ.get("GROWFLOW_SALES_TZ") or "America/Chicago"),
        repo_root=root,
        data_dir=data_dir,
        facts_db=pget("facts_db", "growflow_facts.db")
        if "facts_db" in paths or os.environ.get("GROWFLOW_FACTS_DB")
        else _resolve(root, paths.get("facts_db"), data_dir / "growflow_facts.db"),
        cache_db=_resolve(root, paths.get("cache_db"), data_dir / "retail_dashboard.db"),
        retail_dashboard_json=_resolve(
            root, paths.get("retail_dashboard_json"), data_dir / "retail_dashboard_latest.json"
        ),
        capital_json=_resolve(root, paths.get("capital_json"), data_dir / "retail_capital_latest.json"),
        consignment_json=_resolve(
            root, paths.get("consignment_json"), data_dir / "retail_consignment_latest.json"
        ),
        reconciliation_json=_resolve(
            root, paths.get("reconciliation_json"), data_dir / "retail_reconciliation_latest.json"
        ),
        platform_status_json=_resolve(
            root, paths.get("platform_status_json"), data_dir / "platform_status_latest.json"
        ),
        sales_projection_json=_resolve(
            root, paths.get("sales_projection_json"), data_dir / "sales_projection_latest.json"
        ),
        company_bi_json=_resolve(
            root, paths.get("company_bi_json"), data_dir / "company_bi_report_latest.json"
        ),
        transfer_db=_resolve(root, paths.get("transfer_db"), data_dir / "transfer_receipts.db"),
        consignment_db=_resolve(root, paths.get("consignment_db"), data_dir / "consignment.db"),
        layer2_csv=_resolve(
            root,
            paths.get("layer2_csv"),
            data_dir / "projection_by_category_brand_layer2_recovery.csv",
        ),
        sheets_transactions_db=_resolve(
            root,
            paths.get("sheets_transactions_db"),
            root / "company_bi" / "db" / "sheets_transactions.db",
        ),
        api_host=str(api.get("host") or os.environ.get("GROWFLOW_API_HOST") or "127.0.0.1"),
        api_port=int(api.get("port") or os.environ.get("GROWFLOW_API_PORT") or 8791),
        retail_slo_seconds=int(slo.get("retail_seconds") or 4 * 3600),
        consignment_slo_seconds=int(slo.get("consignment_seconds") or 24 * 3600),
        capital_slo_seconds=int(slo.get("capital_seconds") or 48 * 3600),
        projection_slo_seconds=int(slo.get("projection_seconds") or 12 * 3600),
        fixture_order_count_max=int(fixture.get("order_count_max") or 3),
        fixture_net_sales_max=float(fixture.get("net_sales_max") or 100.0),
    )
