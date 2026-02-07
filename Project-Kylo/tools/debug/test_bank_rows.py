import sys
sys.path.insert(0, ".")
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import parse_csv_transactions
from services.common.config_loader import load_config

cfg = load_config()
sid = "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"
sa = cfg.get("google.service_account_json_path")

# Download BANK tab
csv = download_petty_cash_csv(sid, sa, sheet_name_override="BANK")
lines = csv.split("\n")
print(f"Total CSV lines: {len(lines)}")

# Parse transactions
txns = parse_csv_transactions(csv, header_rows=19)
jgd_txns = [t for t in txns if (t.get("company_id") or "").strip().upper() == "JGD"]

print(f"\nTotal transactions parsed: {len(txns)}")
print(f"JGD transactions: {len(jgd_txns)}")

# Check row indices
if jgd_txns:
    row_indices = [t.get("row_index_0based", 0) for t in jgd_txns]
    print(f"\nRow index range: {min(row_indices)} to {max(row_indices)}")
    print(f"Transactions beyond row 1323: {len([r for r in row_indices if r > 1323])}")
    
    # Check posted flags
    posted = [t for t in jgd_txns if t.get("posted_flag")]
    not_posted = [t for t in jgd_txns if not t.get("posted_flag")]
    print(f"\nPosted: {len(posted)}, Not posted: {len(not_posted)}")
    
    if not_posted:
        not_posted_indices = [t.get("row_index_0based", 0) for t in not_posted]
        print(f"Not posted row range: {min(not_posted_indices)} to {max(not_posted_indices)}")
