import sys
sys.path.insert(0, ".")
from services.intake.csv_downloader import download_petty_cash_csv
from services.common.config_loader import load_config

cfg = load_config()
sid = "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"
sa = cfg.get("google.service_account_json_path")

csv = download_petty_cash_csv(sid, sa, sheet_name_override="BANK")
lines = csv.split("\n")

print(f"Total lines: {len(lines)}")
print(f"\nChecking rows around 1323:")

# Check rows 1320-1330
for i in range(1319, min(1330, len(lines))):
    line = lines[i] if i < len(lines) else ""
    row_num = i + 1  # 1-based
    if line.strip():
        preview = line[:100].replace(",", " | ")
        print(f"Row {row_num}: {preview}")
    else:
        print(f"Row {row_num}: [EMPTY]")

print(f"\nChecking rows 1400-1410:")
for i in range(1399, min(1410, len(lines))):
    line = lines[i] if i < len(lines) else ""
    row_num = i + 1
    if line.strip():
        preview = line[:100].replace(",", " | ")
        print(f"Row {row_num}: {preview}")
