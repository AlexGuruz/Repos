import sqlite3

conn = sqlite3.connect("data/transfer_receipts.db")
q = (
    "SELECT r.transfer_object_id, r.received_at, "
    "COALESCE(NULLIF(TRIM(r.from_name), ''), '(unknown)') AS supplier, "
    "COUNT(*) AS package_lines, SUM(p.original_qty) AS units "
    "FROM transfer_receipt_packages p "
    "JOIN transfer_receipts r ON r.transfer_object_id = p.transfer_object_id "
    "GROUP BY r.transfer_object_id, r.received_at, supplier "
    "ORDER BY r.received_at DESC"
)
rows = conn.execute(q).fetchall()
print("transfer_object_id | received_at | supplier | package_lines | units")
for a, b, c, d, e in rows:
    print(f"{a} | {b} | {c} | {d} | {e}")
conn.close()
