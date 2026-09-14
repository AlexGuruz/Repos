from __future__ import annotations

from pathlib import Path

from services.audit import snapshot as snapshot_mod
from services.audit.paths import latest_snapshot_link, snapshots_root


def _tick_snapshot_names(root: Path) -> list[str]:
    return sorted(p.name for p in root.iterdir() if snapshot_mod._is_tick_snapshot_dir(p))


def test_tick_snapshot_retention_prunes_only_old_tick_snapshots(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    stamps = iter(
        [
            "2026-01-01T00-00-00Z",
            "2026-01-01T00-05-00Z",
            "2026-01-01T00-10-00Z",
            "2026-01-01T00-15-00Z",
        ]
    )
    monkeypatch.setattr(snapshot_mod, "_utc_stamp", lambda: next(stamps))

    instance_id = "JGD_2026"
    root = snapshots_root(instance_id)
    backlog_dir = root / "BACKLOG-BACKLOG-2026-TXN-002-2026-01-01T00-00-00"
    backlog_dir.mkdir(parents=True)
    (backlog_dir / "backlog.json").write_text("{}\n", encoding="utf-8")

    for idx in range(4):
        snap_dir = snapshot_mod.save_tick_snapshot(
            instance_id,
            csv_by_key={f"JGD|PETTY CASH|{idx}": "Date,Amount\n2026-01-01,1.00\n"},
            row_registry={},
            events=[],
            meta={"idx": idx},
            max_snapshots=2,
        )
        assert snap_dir.exists()

    assert _tick_snapshot_names(root) == ["2026-01-01T00-10-00Z", "2026-01-01T00-15-00Z"]
    assert backlog_dir.exists()

    latest = latest_snapshot_link(instance_id)
    assert latest.exists() or latest.is_symlink()
    if latest.is_symlink():
        assert latest.resolve().name == "2026-01-01T00-15-00Z"
    else:
        assert latest.read_text(encoding="utf-8").strip().endswith("2026-01-01T00-15-00Z")
