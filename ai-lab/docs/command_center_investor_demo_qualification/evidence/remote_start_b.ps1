$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"

# Kill prior attempts
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match 'uvicorn|worker_assistant'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2

# Use cmd start so stdio isn't tied to this SSH session; log via -u and shell redirect in detached cmd
$cmd = "set PYTHONPATH=$RepoRoot&& set PYTHONUNBUFFERED=1&& cd /d $RepoRoot&& `"$py`" -u -m uvicorn worker_assistant.app.main:app --host 127.0.0.1 --port 8765 --log-level info 1>> `"$logDir\api.log`" 2>> `"$logDir\api.log.err`""
cmd.exe /c "start /B `"wa`" cmd.exe /c `"$cmd`""
Start-Sleep 10

$report = @()
$report += "cmd=$cmd"
$listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
$report += "listen=$(if ($listen) { $listen.OwningProcess } else { 'none' })"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'uvicorn' } | ForEach-Object {
  $report += "proc=$($_.ProcessId) $($_.CommandLine)"
}
try {
  $r = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $report += "health=$($r.StatusCode) $($r.Content)"
} catch { $report += "health_err=$($_.Exception.Message)" }
if (Test-Path "$logDir\api.log") { $report += "OUT=$(Get-Content `"$logDir\api.log`" -Raw)" }
if (Test-Path "$logDir\api.log.err") { $report += "ERR=$(Get-Content `"$logDir\api.log.err`" -Raw)" }
$report -join "`r`n" | Set-Content "$logDir\start_b_report.txt" -Encoding utf8
Get-Content "$logDir\start_b_report.txt"
