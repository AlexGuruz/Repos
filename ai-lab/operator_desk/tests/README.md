# Operator Desk tests

```powershell
cd E:\Repos\ai-lab
$env:PYTHONPATH = "."
python -m pytest operator_desk/tests -q
```

Tests are offline: fixture Jobs dir via `OPERATOR_JOBS_DIR`; Growflow snapshot temp files; approvals mocked.
