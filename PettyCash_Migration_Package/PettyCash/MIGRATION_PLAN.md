# 🚀 PETTY CASH SORTER - COMPLETE MIGRATION PLAN

## 📋 OVERVIEW
This plan will help you move the entire Petty Cash Sorter program (including monitor, dependencies, and Python environment) from your portable drive to your actual PC.

## 🎯 MIGRATION STEPS

### **STEP 1: PREPARATION (On Portable Drive)**

#### 1.1 Create Migration Package
```bash
# Create a complete backup of the entire project
mkdir PettyCash_Migration_Package
xcopy /E /I /H /Y "D:\ScriptHub\PettyCash" "PettyCash_Migration_Package"
```

#### 1.2 Export Current Environment
```bash
# Export current Python packages
venv\Scripts\pip freeze > requirements_migration.txt
```

#### 1.3 Create Migration Script
```python
# Create a migration verification script
python create_migration_verification.py
```

### **STEP 2: TRANSFER TO PC**

#### 2.1 Copy Files
- Copy entire `PettyCash_Migration_Package` folder to your PC
- Recommended location: `C:\ScriptHub\PettyCash` or `C:\Users\[YourUsername]\Documents\ScriptHub\PettyCash`

#### 2.2 Transfer Python Environment
- Copy the `venv` folder (if you want to keep the exact same environment)
- OR recreate the environment on PC (recommended)

### **STEP 3: PC SETUP**

#### 3.1 Install Python (if not already installed)
- Download Python 3.11+ from python.org
- Install with "Add to PATH" option checked
- Verify installation: `python --version`

#### 3.2 Create Virtual Environment
```bash
cd C:\ScriptHub\PettyCash
python -m venv venv
venv\Scripts\activate
```

#### 3.3 Install Dependencies
```bash
pip install -r requirements.txt
# OR if you exported specific versions:
pip install -r requirements_migration.txt
```

### **STEP 4: CONFIGURATION UPDATES**

#### 4.1 Update File Paths
- Update `config/system_config.json` if needed
- Check database paths in `database_manager.py`
- Verify Google Sheets service account path

#### 4.2 Test Core Components
```bash
# Test database connection
python -c "from database_manager import DatabaseManager; db = DatabaseManager(); print('Database OK')"

# Test Google Sheets connection
python -c "from google_sheets_integration import GoogleSheetsIntegration; gs = GoogleSheetsIntegration(); print('Google Sheets OK')"

# Test AI matcher
python -c "from ai_rule_matcher_enhanced import AIEnhancedRuleMatcher; ai = AIEnhancedRuleMatcher(); print('AI Matcher OK')"
```

### **STEP 5: LAUNCH MONITOR**

#### 5.1 Start the Monitor
```bash
python demo_rule_management.py
```

#### 5.2 Verify Monitor Access
- Open browser to `http://localhost:5000`
- Check all tabs and functionality
- Test rule editing and dropdowns

### **STEP 6: TEST FULL SYSTEM**

#### 6.1 Test Petty Cash Sorter
```bash
python petty_cash_sorter_final_comprehensive.py
```

#### 6.2 Verify Data Processing
- Check that transactions are processed correctly
- Verify Google Sheets updates
- Confirm rule matching works

## 🔧 CRITICAL FILES TO PRESERVE

### **Core Application Files:**
- `ai_rule_matcher_enhanced.py` - AI matching logic
- `real_time_monitor_enhanced.py` - Web monitor
- `database_manager.py` - Database operations
- `google_sheets_integration.py` - Google Sheets API
- `petty_cash_sorter_final_comprehensive.py` - Main sorter

### **Configuration Files:**
- `config/service_account.json` - Google API credentials
- `config/system_config.json` - System settings
- `config/layout_map.json` - Sheet structure mapping
- `config/petty_cash.db` - Main database
- `requirements.txt` - Python dependencies

### **Data Files:**
- `config/petty_cash.db` - All rules and transaction data
- `config/layout_map_cache.json` - Cached sheet layouts
- `logs/` directory - Audit trails and logs

## ⚠️ IMPORTANT CONSIDERATIONS

### **Google Sheets API:**
- The `service_account.json` contains API credentials
- These credentials are tied to the Google Cloud project
- Should work on any machine with internet access
- No need to regenerate unless you want new credentials

### **Database:**
- `petty_cash.db` contains all your rules and transaction history
- This is the most critical file to preserve
- Consider backing up before migration

### **File Paths:**
- Most paths are relative to the project directory
- Should work automatically on new PC
- Check `system_config.json` for any absolute paths

### **Python Version:**
- Ensure PC has Python 3.11+ installed
- Virtual environment will isolate dependencies
- All packages will be reinstalled fresh

## 🚨 TROUBLESHOOTING

### **Common Issues:**

1. **Python not found:**
   - Install Python from python.org
   - Add to PATH during installation

2. **Package installation errors:**
   - Update pip: `python -m pip install --upgrade pip`
   - Install Visual C++ build tools if needed

3. **Database connection errors:**
   - Check file permissions
   - Ensure `config/` directory exists

4. **Google Sheets API errors:**
   - Verify internet connection
   - Check service account credentials
   - Ensure Google Cloud project is active

5. **Monitor not starting:**
   - Check if port 5000 is available
   - Try different port in `system_config.json`
   - Check firewall settings

## ✅ VERIFICATION CHECKLIST

- [ ] Python 3.11+ installed on PC
- [ ] Virtual environment created and activated
- [ ] All dependencies installed successfully
- [ ] Database connects without errors
- [ ] Google Sheets API works
- [ ] Monitor starts and is accessible
- [ ] Rule editing works in monitor
- [ ] Dropdowns show correct data
- [ ] Petty cash sorter processes transactions
- [ ] Google Sheets updates correctly

## 📞 SUPPORT

If you encounter issues during migration:
1. Check the troubleshooting section above
2. Verify all critical files were transferred
3. Test components individually
4. Check Python and package versions match

## 🎉 SUCCESS INDICATORS

You'll know the migration is successful when:
- Monitor loads at `http://localhost:5000`
- All tabs show data correctly
- Rule editing works with dynamic dropdowns
- Petty cash sorter processes transactions
- Google Sheets updates with new data
- No error messages in console

---

**Migration Time Estimate:** 30-60 minutes
**Difficulty Level:** Moderate
**Risk Level:** Low (with proper backup) 