# 🚀 PETTY CASH SYSTEM MIGRATION PACKAGE

## 📦 Package Overview
This package contains everything needed to run the Petty Cash Sorter system on a dedicated PC, including all Python scripts, databases, configuration files, and the complete WinPython64 environment.

**Package Size:** ~472 MB  
**Total Files:** 10,431 files  
**Created:** July 25, 2025

## 📁 Package Structure

```
PettyCash_Migration_Package/
├── PettyCash/                    # Main application files
│   ├── THe.py                    # Main petty cash sorter
│   ├── real_time_monitor_enhanced.py  # Enhanced monitoring dashboard
│   ├── database_manager.py       # Database operations
│   ├── csv_downloader_fixed.py   # CSV data downloader
│   ├── ai_rule_matcher_enhanced.py  # AI rule matching system
│   ├── google_sheets_integration.py  # Google Sheets integration
│   ├── config_manager.py         # Configuration management
│   ├── processed_transaction_manager.py  # Transaction processing
│   ├── performance_monitor.py    # Performance monitoring
│   ├── audit_and_reporting.py    # Audit and reporting
│   ├── api_rate_limiter.py       # API rate limiting
│   ├── config/                   # Configuration files
│   │   ├── system_config.json    # Main system configuration
│   │   ├── service_account.json  # Google API credentials
│   │   ├── layout_map.json       # Sheet layout mapping
│   │   ├── petty_cash.db         # Main database
│   │   └── [other config files]
│   ├── exports/                  # Data exports
│   ├── LOCKDOWN/                 # Security system
│   └── [all other Python scripts]
└── WinPython64/                  # Complete Python environment
    ├── python-3.12.4.amd64/      # Python interpreter
    ├── scripts/                  # Python scripts
    ├── settings/                 # Python settings
    └── [all executable files]
```

## 🔧 Installation Instructions

### Step 1: Extract the Package
1. Copy the entire `PettyCash_Migration_Package` folder to your dedicated PC
2. Extract or place it in a convenient location (e.g., `C:\PettyCash_System\`)

### Step 2: Install Python Dependencies
Open a command prompt in the PettyCash folder and run:
```bash
# Navigate to the PettyCash directory
cd C:\PettyCash_System\PettyCash_Migration_Package\PettyCash

# Install required Python packages
pip install gspread google-auth flask flask-socketio pandas numpy
```

### Step 3: Verify Google API Credentials
1. Check that `config/service_account.json` exists and contains valid Google API credentials
2. Ensure the service account has access to the Google Sheets you're working with

### Step 4: Test the System
1. **Test Database Connection:**
   ```bash
   python check_database_schema.py
   ```

2. **Test Google Sheets Connection:**
   ```bash
   python test_sheet_access.py
   ```

3. **Start Monitoring (Optional):**
   ```bash
   python run_monitor_only.py
   ```

4. **Run Main Application:**
   ```bash
   python THe.py
   ```

## 🚀 Quick Start Commands

### Launch Monitoring Dashboard
```bash
python real_time_monitor_enhanced.py
```

### Run Main Petty Cash Sorter
```bash
python THe.py
```

### Run Test Mode
```bash
python run_test_monitor.py
```

### Run Demo Mode
```bash
python run_slow_demo.py
```

## 📋 Critical Files Description

### 🔑 Essential Configuration Files
- **`config/service_account.json`** - Google API credentials (KEEP SECURE!)
- **`config/system_config.json`** - Main system configuration
- **`config/layout_map.json`** - Google Sheets layout mapping
- **`config/petty_cash.db`** - Main transaction database

### 🐍 Core Python Scripts
- **`THe.py`** - Main application entry point
- **`real_time_monitor_enhanced.py`** - Web-based monitoring dashboard
- **`database_manager.py`** - Database operations and management
- **`google_sheets_integration.py`** - Google Sheets API integration
- **`ai_rule_matcher_enhanced.py`** - AI-powered rule matching system

### 🛡️ Security & Monitoring
- **`LOCKDOWN/`** - Security system files
- **`performance_monitor.py`** - Performance tracking
- **`audit_and_reporting.py`** - Audit logging and reporting

## ⚠️ Important Notes

### Security Considerations
1. **Google API Credentials**: The `service_account.json` file contains sensitive credentials
   - Keep this file secure and don't share it
   - Consider encrypting it on the new system
   - Regularly rotate the credentials

2. **Database Files**: The `.db` files contain all transaction data
   - Backup regularly
   - Keep in a secure location
   - Consider encryption for sensitive data

### System Requirements
- **Windows 10/11** (64-bit)
- **Internet Connection** (for Google Sheets integration)
- **4GB RAM minimum** (8GB recommended)
- **2GB free disk space**

### Network Requirements
- **Outbound HTTPS** (for Google Sheets API)
- **Port 5000** (for monitoring dashboard, if used)
- **Firewall exceptions** for Python and the application

## 🔧 Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt  # if available
   ```

2. **Google API Errors**
   - Verify `service_account.json` is valid
   - Check Google Sheets permissions
   - Ensure internet connectivity

3. **Database Errors**
   - Check file permissions on `.db` files
   - Verify SQLite is working
   - Check disk space

4. **Monitoring Dashboard Issues**
   - Check if port 5000 is available
   - Verify Flask installation
   - Check firewall settings

### Log Files
Check these log files for errors:
- `logs/petty_cash_sorter_final.log`
- `logs/google_sheets_integration.log`
- `LOCKDOWN/lockdown.log`

## 📞 Support

If you encounter issues:
1. Check the log files in the `logs/` directory
2. Run diagnostic scripts: `check_*.py` files
3. Test individual components: `test_*.py` files
4. Review the documentation files: `*.md` files

## 🔄 Updates and Maintenance

### Regular Maintenance
1. **Backup databases** weekly
2. **Check log files** for errors
3. **Update Python packages** monthly
4. **Rotate API credentials** quarterly

### System Updates
1. Keep WinPython64 updated
2. Monitor for security updates
3. Test updates in a staging environment first

---

**Migration Package Created:** July 25, 2025  
**Total Size:** 472 MB  
**Files Included:** 10,431  
**Status:** ✅ Ready for deployment 