# Google Sheets XLSX Downloader

## Overview

This system automatically downloads Google Sheets as XLSX files on a schedule (every 24 hours). This can significantly optimize your petty cash sorter by eliminating API calls and working with local Excel files instead.

## Benefits

✅ **Eliminates API Quota Issues** - No more rate limiting problems  
✅ **Faster Processing** - Local Excel files are much faster than API calls  
✅ **Offline Capability** - Work with data even when internet is down  
✅ **Version Control** - Keep timestamped backups of all downloads  
✅ **Scheduled Automation** - Runs automatically every 24 hours  

## How It Works

### 1. Scheduled Downloads
- Downloads run automatically every 24 hours at 2:00 AM
- Creates timestamped files: `20250115_020000_2025 JGD Financials.xlsx`
- Maintains symlinks to latest versions: `2025 JGD Financials.xlsx` → latest file

### 2. Files Downloaded
- **2025 JGD Financials.xlsx** - Main petty cash spreadsheet
- **JGD Truth.xlsx** - Mapping rules spreadsheet

### 3. File Structure
```
downloads/
├── 20250115_020000_2025 JGD Financials.xlsx  (timestamped)
├── 20250115_020000_JGD Truth.xlsx            (timestamped)
├── 2025 JGD Financials.xlsx                  (symlink to latest)
└── JGD Truth.xlsx                            (symlink to latest)
```

## Usage

### Quick Start
1. **One-time download (for testing):**
   ```
   run_downloader_once.bat
   ```

2. **Start scheduler (runs every 24 hours):**
   ```
   run_downloader.bat
   ```

### Manual Usage
```bash
# Run once
python google_sheets_downloader.py --once

# Start scheduler
python google_sheets_downloader.py
```

## Integration with Petty Cash Sorter

### Current Data Movement (API-heavy):
```
Google Sheets API → Process → Google Sheets API → Update
```

### New Data Movement (Excel-based):
```
Google Sheets → XLSX Download → Process → Excel Files → Update
```

### Benefits for Your System:
1. **Zero API calls during processing** - All data is local
2. **Much faster processing** - No network delays
3. **Better error handling** - Local file validation
4. **Version control** - Keep historical snapshots
5. **Offline capability** - Process without internet

## Configuration

### Modify Download Schedule
Edit `google_sheets_downloader.py`:
```python
# Change from 2:00 AM to any time
schedule.every().day.at("02:00").do(self.run_scheduled_download)

# Or change frequency
schedule.every(12).hours.do(self.run_scheduled_download)  # Every 12 hours
schedule.every().monday.at("09:00").do(self.run_scheduled_download)  # Weekly
```

### Add More Sheets
Edit the `sheets_to_download` dictionary:
```python
self.sheets_to_download = {
    "petty_cash": {
        "url": "your_sheet_url",
        "filename": "Your Sheet.xlsx"
    },
    # Add more sheets here...
}
```

## Requirements

- Python 3.7+
- Google Service Account credentials (`config/service_account.json`)
- Internet connection for downloads

## Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements_downloader.txt
   ```

2. **Ensure service account file exists:**
   ```
   config/service_account.json
   ```

3. **Run the downloader:**
   ```bash
   python google_sheets_downloader.py --once
   ```

## Logs

All activity is logged to:
- `logs/sheets_downloader.log` - Detailed logs
- Console output - Real-time status

## Troubleshooting

### Common Issues

1. **Service account not found:**
   - Ensure `config/service_account.json` exists
   - Check file permissions

2. **Download fails:**
   - Check internet connection
   - Verify Google Sheets URLs are correct
   - Check service account permissions

3. **Scheduler not running:**
   - Ensure script is running continuously
   - Check system time zone settings

### Manual Recovery
If downloads fail, you can:
1. Run `run_downloader_once.bat` to download immediately
2. Check logs in `logs/sheets_downloader.log`
3. Verify service account permissions in Google Cloud Console

## Next Steps

Once this is working, you can modify your `petty_cash_sorter_final.py` to:
1. Use local Excel files instead of Google Sheets API
2. Process data much faster without API limitations
3. Add better error handling and validation
4. Implement incremental processing (only new transactions)

This approach will solve your API quota issues and make the system much more reliable! 