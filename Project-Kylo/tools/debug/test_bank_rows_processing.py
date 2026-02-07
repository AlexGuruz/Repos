import sys
sys.path.insert(0, ".")
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.common.config_loader import load_config
import csv as csvlib

cfg = load_config()
sid = "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"
sa = cfg.get("google.service_account_json_path")

print("=== Testing BANK Tab Row Processing ===\n")

# Download BANK tab
csv_content = download_petty_cash_csv(sid, sa, sheet_name_override="BANK")
lines = csv_content.split("\n")

print(f"Total CSV lines: {len(lines)}\n")

# Check raw data for rows 1340-1345
print("=== Raw CSV Data for Rows 1340-1345 ===")
for i, line in enumerate(lines[19:], start=20):
    if 1340 <= i <= 1345:
        if line.strip():
            try:
                row = next(csvlib.reader([line]))
                print(f"Row {i}:")
                print(f"  Column A (0): '{row[0] if len(row) > 0 else ''}'")
                print(f"  Column B (1): '{row[1] if len(row) > 1 else ''}'")
                print(f"  Column C (2): '{row[2] if len(row) > 2 else ''}'")
                print(f"  Column D (3): '{row[3] if len(row) > 3 else ''}'")
                print(f"  Column E (4): '{row[4] if len(row) > 4 else ''}'")
                print(f"  Column F (5): '{row[5] if len(row) > 5 else ''}'")
                print()
            except Exception as e:
                print(f"Row {i}: Error parsing - {e}\n")

# Test CSV processor
print("\n=== Testing CSV Processor ===")
processor = PettyCashCSVProcessor(csv_content, header_rows=19, source_tab="BANK")
txns = list(processor.parse_transactions())

print(f"Total transactions parsed: {len(txns)}")

# Check for transactions beyond row 1323
beyond_1323 = [t for t in txns if t.get("row_index_0based", 0) > 1323]
print(f"Transactions beyond row 1323: {len(beyond_1323)}")

# Check specifically for row 1340
row_1340_txns = [t for t in txns if t.get("row_index_0based", 0) == 1340]
print(f"\nTransactions at row 1340: {len(row_1340_txns)}")
if row_1340_txns:
    for t in row_1340_txns:
        print(f"  Company: {t.get('company_id')}")
        print(f"  Description: {t.get('description')}")
        print(f"  Amount: {t.get('amount_cents', 0)/100}")
        print(f"  Date: {t.get('posted_date')}")
        print(f"  Posted flag: {t.get('posted_flag')}")
else:
    print("  [ERROR] Row 1340 was NOT parsed!")

# Check JGD transactions beyond 1323
jgd_beyond_1323 = [t for t in beyond_1323 if (t.get("company_id") or "").strip().upper() == "JGD"]
print(f"\nJGD transactions beyond row 1323: {len(jgd_beyond_1323)}")
if jgd_beyond_1323:
    print("\nFirst 5 JGD transactions beyond 1323:")
    for t in jgd_beyond_1323[:5]:
        print(f"  Row {t.get('row_index_0based')}: {t.get('description', '')[:50]} - Company: {t.get('company_id')} - Posted: {t.get('posted_flag')}")

