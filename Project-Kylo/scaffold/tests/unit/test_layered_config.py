from __future__ import annotations

from pathlib import Path

import pytest


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_layered_config_resolution_order(monkeypatch, tmp_path: Path):
    # Arrange a layered config directory
    cfg_dir = tmp_path / "config"
    _write(
        cfg_dir / "global.yaml",
        """
version: 1
runtime:
  dry_run: false
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: C:\\\\secrets\\\\sa.json
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {}
routing:
  mover:
    batch_size: 500
""".lstrip(),
    )
    _write(
        cfg_dir / "companies" / "JGD.yaml",
        """
version: 1
sheets:
  companies:
    - key: JGD
      workbook_url: https://docs.google.com/spreadsheets/d/abc123
      tabs:
        intake: PETTY CASH
        output: CLEAN TRANSACTIONS
routing:
  mover:
    batch_size: 111
year_workbooks_active: ["2025", "2026"]
""".lstrip(),
    )
    _write(
        cfg_dir / "instances" / "JGD_2025.yaml",
        """
version: 1
instance:
  id: JGD_2025
  company_key: JGD
year_workbooks_active: ["2025"]
""".lstrip(),
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_2025")

    # Act
    from services.common.config_loader import load_config

    cfg = load_config()

    # Assert: required values come from global, overrides from company/instance
    # YAML escaping on Windows can preserve backslashes; just assert the path shape.
    sa_path = cfg.get("google.service_account_json_path")
    assert isinstance(sa_path, str)
    assert "secrets" in sa_path.lower()
    assert sa_path.lower().endswith("sa.json")
    assert cfg.get("routing.mover.batch_size") == 111  # company overrides global
    assert cfg.get("year_workbooks_active") == ["2025"]  # instance overrides company
    assert [c.get("key") for c in (cfg.get("sheets.companies") or [])] == ["JGD"]


def test_layered_config_company_key_parsing(monkeypatch, tmp_path: Path):
    cfg_dir = tmp_path / "config"
    _write(
        cfg_dir / "global.yaml",
        """
version: 1
runtime:
  dry_run: true
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: C:\\\\secrets\\\\sa.json
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {}
""".lstrip(),
    )
    _write(
        cfg_dir / "companies" / "JGD.yaml",
        """
version: 1
sheets:
  companies:
    - key: JGD
      workbook_url: https://docs.google.com/spreadsheets/d/abc123
      tabs:
        intake: PETTY CASH
        output: CLEAN TRANSACTIONS
""".lstrip(),
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD:2025")

    from services.common.config_loader import load_config

    cfg = load_config()
    assert [c.get("key") for c in (cfg.get("sheets.companies") or [])] == ["JGD"]


def test_layered_config_falls_back_when_no_global(monkeypatch, tmp_path: Path):
    # If config/global.yaml doesn't exist, we should not force layered mode;
    # legacy config path should still work.
    cfg_dir = tmp_path / "config"
    _write(
        cfg_dir / "kylo.config.yaml",
        """
version: 1
runtime:
  dry_run: true
  log_level: INFO
  timezone: America/Chicago
google:
  service_account_json_path: C:\\\\secrets\\\\sa.json
sheets:
  companies: []
database:
  global_dsn: postgresql://postgres:kylo@localhost:5433/kylo_global
  per_company: false
  company_dsns: {}
posting:
  sheets:
    apply: false
""".lstrip(),
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_2025")

    from services.common.config_loader import load_config

    cfg = load_config()
    assert cfg.get("posting.sheets.apply") is False

