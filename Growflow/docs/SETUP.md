# Growflow Setup

## Prerequisites

- Python 3.10+
- Google Cloud service account (for Sheets sync, if used)
- GrowFlow API credentials (if available)

## Initial Setup

1. **Clone or copy this repo**

2. **Create config**
   ```powershell
   cd E:\Repos\Growflow
   copy config\config.example.yaml config\config.yaml
   # Edit config.yaml with your credentials
   ```

3. **Install dependencies** (when requirements.txt exists)
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

## Integration Points

| System    | Purpose                                   |
|-----------|-------------------------------------------|
| NUGZ EXPENSES | Grow Flow is column 10 in expense sheet |
| Kylo      | Petty cash / transaction flow            |
| ScriptHub | Bank sync, expense posting               |

## Notes

- GrowFlow automation was previously "documented separately" per ScriptHub PRE_DELETE_CHECKLIST
- No original code was recovered; this structure is a fresh start
