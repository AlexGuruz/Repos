from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.build_projection_by_category_brand import _load_latest_unit_cost_cents_by_product_object_id


def test_load_latest_unit_cost_map(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE product_landed_cost_current (
                product_object_id TEXT PRIMARY KEY,
                unit_cost_cents REAL
            );
            """
        )
        conn.execute(
            "INSERT INTO product_landed_cost_current(product_object_id, unit_cost_cents) VALUES (?, ?)",
            ("P1", 3500.2),
        )
        conn.execute(
            "INSERT INTO product_landed_cost_current(product_object_id, unit_cost_cents) VALUES (?, ?)",
            ("P2", None),
        )
        conn.commit()
    finally:
        conn.close()

    m = _load_latest_unit_cost_cents_by_product_object_id(db)
    assert m["P1"] == 3500
    assert "P2" not in m

