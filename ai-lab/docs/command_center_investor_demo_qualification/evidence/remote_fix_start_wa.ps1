$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$logDir = "C:\worker\logs\worker_assistant"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# Kill stale listeners on 8765 owned by python
Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
}
Get-Process python,pythonw -ErrorAction SilentlyContinue | Where-Object {
  try {
    $c = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    $c -match 'worker_assistant|uvicorn'
  } catch { $false }
} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2
$env:PYTHONPATH = $RepoRoot
Set-Location $RepoRoot

& $pythonExe -c "from worker_assistant.app.main import app; print('import_ok', app.title if hasattr(app,'title') else 'app')" *> "$logDir\diag_import.txt"

$out = Join-Path $logDir "api.log"
$err = Join-Path $logDir "api.log.err"
Remove-Item $out,$err -ErrorAction SilentlyContinue

$p = Start-Process -FilePath $pythonExe `
  -ArgumentList "-m","uvicorn","worker_assistant.app.main:app","--host","127.0.0.1","--port","8765","--log-level","info" `
  -WorkingDirectory $RepoRoot `
  -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput $out `
  -RedirectStandardError $err

"started_pid=$($p.Id) exited=$($p.HasExited)" | Set-Content "$logDir\start_pid.txt" -Encoding ascii
Start-Sleep -Seconds 6
"exited_after_wait=$($p.HasExited)" | Add-Content "$logDir\start_pid.txt" -Encoding ascii

try {
  $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765/health" -UseBasicParsing -TimeoutSec 5
  "status=$($r.StatusCode) body=$($r.Content)" | Set-Content "$logDir\health_after_start.txt" -Encoding ascii
} catch {
  $_.Exception.Message | Set-Content "$logDir\health_after_start.txt" -Encoding ascii
}

Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,OwningProcess |
  Format-List | Out-String | Set-Content "$logDir\listen.txt" -Encoding ascii

if (Test-Path $err) { Get-Content $err -Raw | Set-Content "$logDir\err_tail.txt" -Encoding ascii }
if (Test-Path $out) { Get-Content $out -Raw | Set-Content "$logDir\out_tail.txt" -Encoding ascii }
