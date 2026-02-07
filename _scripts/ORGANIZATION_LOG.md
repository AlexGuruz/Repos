# D:\ Root Files Organization Log

**Date:** 2026-01-27  
**Action:** Organized miscellaneous root files into structured directories

---

## New Directory Structure

```
D:\
├── _archive\
│   └── 2026-01-27\
│       └── root_files\          # Archived migration docs
│           ├── README_MIGRATION.md
│           └── requirements.txt
├── _scripts\
│   ├── setup\                    # Environment setup scripts
│   │   ├── Enviroment_Setup.bat
│   │   ├── GitPortable_Setup.bat
│   │   └── setup_migration.bat
│   └── utilities\                # Standalone utility scripts
│       ├── heart_drawing.py
│       └── main.py
├── _data\
│   ├── sales_exports\            # Historical sales data
│   │   ├── Nugz  (7-31)-(5-1) OrderItems.csv
│   │   ├── Nugz (1-31)-(11-1)  OrderItems.csv
│   │   ├── Nugz (4-30)-(2-1) OrderItems.csv
│   │   └── Nugz (10-15)-(8-1) OrderItems.csv
│   └── analytics\                # Analytics files
│       └── sales_metrics.xlsx
├── _projects\
│   └── exports\                  # Project archives
│       └── Project-Kylo-export.zip
└── _config\                      # Configuration files
    ├── PASSIVE_SCRIPTS.code-workspace
    ├── syncthing_sync_log.txt
    └── gcloud
```

---

## Files Moved

### Petty Cash Migration → `_archive/2026-01-27/root_files/`
- `README_MIGRATION.md`
- `setup_migration.bat` → `_scripts/setup/`
- `requirements.txt`

### Environment Setup → `_scripts/setup/`
- `Enviroment_Setup.bat`
- `GitPortable_Setup.bat`

### Utility Scripts → `_scripts/utilities/`
- `heart_drawing.py`
- `main.py`

### Data Files → `_data/`
- `Nugz *.csv` → `_data/sales_exports/`
- `sales_metrics.xlsx` → `_data/analytics/`

### Archives → `_projects/exports/`
- `Project-Kylo-export.zip`

### Configuration → `_config/`
- `PASSIVE_SCRIPTS.code-workspace`
- `syncthing_sync_log.txt`
- `gcloud`

---

## Benefits

1. **Clean Root:** D:\ root is now organized
2. **Easy Navigation:** Files grouped by purpose
3. **Better Organization:** Logical directory structure
4. **Preserved Access:** All files still accessible, just organized

---

## Accessing Files

### Setup Scripts
```powershell
cd D:\_scripts\setup
.\Enviroment_Setup.bat
.\GitPortable_Setup.bat
```

### Utility Scripts
```powershell
cd D:\_scripts\utilities
python heart_drawing.py
python main.py
```

### Data Files
```powershell
# Sales exports
cd D:\_data\sales_exports

# Analytics
cd D:\_data\analytics
```

### Archives
```powershell
cd D:\_projects\exports
# Project-Kylo-export.zip is here
```

---

**Organization Complete:** 2026-01-27
