from __future__ import annotations

from services.rules_promoter import service


class _Cursor:
    def __init__(self, statements):
        self.statements = statements

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.statements.append(str(sql))


class _Conn:
    def __init__(self):
        self.statements = []

    def cursor(self):
        return _Cursor(self.statements)


def test_apply_snapshot_to_company_upserts_without_truncating_active_rules():
    conn = _Conn()

    service._apply_snapshot_to_company(
        conn,
        [
            (
                "content-hash-1",
                {
                    "source": "Vendor",
                    "target_sheet": "Ops",
                    "target_header": "Supplies",
                    "approved": True,
                },
            )
        ],
    )

    joined = "\n".join(conn.statements).upper()
    assert "TRUNCATE" not in joined
    assert "INSERT INTO APP.RULES_ACTIVE" in joined
    assert "ON CONFLICT" in joined
