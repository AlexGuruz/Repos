$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$logDir = "C:\worker\logs\worker_assistant"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$env:PYTHONPATH = $RepoRoot
Set-Location $RepoRoot
& $pythonExe -c "import worker_assistant.app.main; print('import_ok')" 2>&1 | Out-File "$logDir\import_test.txt" -Encoding utf8
$p = Start-Process -FilePath $pythonExe -ArgumentList "-m","uvicorn","worker_assistant.app.main:app","--host","0.0.0.0","--port","8765" -PassThru -WindowStyle Hidden -RedirectStandardOutput "$logDir\api.log" -RedirectStandardError "$logDir\api.log.err"
"started_pid=$($p.Id)" | Out-File "$logDir\start_pid.txt" -Encoding utf8
Start-Sleep -Seconds 5
try {
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -TimeoutSec 5
  $h | ConvertTo-Json -Compress | Out-File "$logDir\health_after_start.txt" -Encoding utf8
} catch {
  $_.Exception.Message | Out-File "$logDir\health_after_start.txt" -Encoding utf8
}
