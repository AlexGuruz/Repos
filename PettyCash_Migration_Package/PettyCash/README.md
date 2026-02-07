# Petty Cash Sorter – Quick Start for AI Collaboration

Welcome! This workspace is now clean and ready for you to resume work with the AI assistant. Here's everything you (and the AI) need to pick up right where you left off.

---

## 🚀 Project Summary
- **Purpose:** Automate the sorting and categorization of Petty Cash transactions using Google Sheets, with robust batching to avoid API quota issues.
- **Key Feature:** Batch range update method to minimize API calls and preserve formatting/logic in Google Sheets.

---

## 🖥️ **Primary User Interface: Desktop Widget**
**🎯 RECOMMENDED: Use the Desktop Widget for daily operations**

### **Launch the Desktop Widget:**
```bash
# Option 1: Double-click the batch file
launch_enhanced_widget.bat

# Option 2: Run directly with Python
python desktop_widget_enhanced.py
```

### **Desktop Widget Features:**
- 📊 **Real-time monitoring** of both Header Monitor and Petty Cash Sorter
- 🔄 **One-click processing** with live progress updates
- ⚡ **Force Process All** button for bulk transaction processing
- 📈 **Live status tracking** with timestamps
- 🎛️ **Configurable intervals** (12 hours for headers, 5 minutes for petty cash)
- 🗑️ **System tray integration** (minimize to tray with Escape key)
- 📝 **Separate activity logs** for each system

---

## 📂 Where to Find the Main Code
- **Main Sorter (current):**
  - `petty_cash_sorter_optimized.py`  ← Use this for all new batch/range logic
- **Desktop Widget (primary UI):**
  - `desktop_widget_enhanced.py`  ← **RECOMMENDED for daily use**
- **AI-Enhanced Sorter:**
  - `petty_cash_sorter_ai_enhanced.py`  ← For dynamic quota/AI logic
- **Quota-Managed Sorter:**
  - `petty_cash_sorter_quota_managed.py`  ← For advanced quota management
- **Monitoring/Widget:**
  - `petty_cash_monitor.py`, `live_monitor.py`, `ai_enhanced_widget.py`
- **Config:**
  - `config/service_account.json` (Google API credentials)
  - `config/ai_quota_config.json` (AI quota settings)

---

## 📖 Where to Find Documentation
- **Project Overview, Batch Plan, and Usage:**
  - This `README.md` (for quick onboarding)
  - For detailed plans, see `backup_old_files/` (contains all previous docs, plans, and reviews)

---

## ▶️ How to Run the Main Scripts

### **🎯 Primary Method: Desktop Widget**
```bash
# Launch the desktop widget (RECOMMENDED)
launch_enhanced_widget.bat
```

### **Alternative Methods:**
1. **Activate your virtual environment:**
   ```bash
   venv\Scripts\activate
   ```
2. **Run the main sorter:**
   ```bash
   python petty_cash_sorter_optimized.py
   ```
3. **Run the AI-enhanced sorter:**
   ```bash
   python petty_cash_sorter_ai_enhanced.py
   ```
4. **Monitor progress:**
   ```bash
   python petty_cash_monitor.py
   python live_monitor.py
   ```

---

## 💡 How to Resume Work with the AI
- **Tell the AI:**
  > "Workspace is clean. Resume Petty Cash batch range update implementation using petty_cash_sorter_optimized.py."
- **Or:**
  > "Help me implement/test/optimize the batch update logic in the current sorter."

---

## 📝 Tips for Efficient Collaboration
- **Reference this README** for file locations and next steps.
- **All old files and docs** are in `backup_old_files/` if you need to restore or review anything.
- **Keep the main sorter (`petty_cash_sorter_optimized.py`) as the primary file** for new logic.
- **Ask the AI to generate, test, or explain code as needed.**
- **For config or credentials issues, check the `config/` folder.**

---

**You're ready to continue development or hand off to the AI at any time!**

_Last updated: December 2024_ 