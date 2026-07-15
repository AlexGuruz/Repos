$ErrorActionPreference = "Continue"
$logDir = "C:\worker\logs\worker_assistant"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$report = Join-Path $logDir "diag_report.txt"
$lines = @()

$lines += "=== time $(Get-Date -Format o) ==="
$lines += "hostname=$(hostname)"

# Listeners
$listen = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($listen) {
  foreach ($l in $listen) {
    $lines += "LISTEN $($l.LocalAddress):$($l.LocalPort) pid=$($l.OwningProcess)"
    try {
      $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($l.OwningProcess)"
      $lines += "  cmd=$($proc.CommandLine)"
    } catch {}
  }
} else {
  $lines += "LISTEN none on 8765"
}

# python processes mentioning worker/uvicorn
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
  if ($_.CommandLine -match 'worker_assistant|uvicorn') {
    $lines += "PROC id=$($_.ProcessId) cmd=$($_.CommandLine)"
  }
}

# try import + bind probe inside venv
$env:PYTHONPATH = "C:\worker\worker_ai"
Set-Location C:\worker\worker_ai
$py = "C:\worker\worker_ai\.venv\Scripts\python.exe"
$probe = & $py -c @"
import socket, traceback
print('py_ok')
try:
    from worker_assistant.app.main import app
    print('import_ok', getattr(app, 'title', type(app)))
except Exception as e:
    print('import_fail', e)
    traceback.print_exc()
s = socket.socket(); print('connect_ex', s.connect_ex(('127.0.0.1', 8765))); s.close()
"@ 2>&1
$lines += "=== probe ==="
$lines += ($probe | Out-String)

# Attempt brief uvicorn in-process via subprocess with timeout, capture both streams to files
$out = Join-Path $logDir "fg_try.out"
$err = Join-Path $logDir "fg_try.err"
Remove-Item $out,$err -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $py `
  -ArgumentList "-m","uvicorn","worker_assistant.app.main:app","--host","127.0.0.1","--port","8765","--log-level","debug" `
  -WorkingDirectory "C:\worker\worker_ai" `
  -PassThru -WindowStyle Hidden `
  -RedirectStandardOutput $out `
  -RedirectStandardError $err
$lines += "started $($p.Id)"
Start-Sleep -Seconds 8
$lines += "has_exited=$($p.HasExited) exit=$($p.ExitCode)"
$listen2 = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
$lines += "listen_after=$(if ($listen2) { ($listen2 | ForEach-Object { $_.OwningProcess }) -join ',' } else { 'none' })"
try {
  $r = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 3
  $lines += "health=$($r.StatusCode) $($r.Content)"
} catch {
  $lines += "health_err=$($_.Exception.Message)"
}
if (Test-Path $out) { $lines += "OUT:"; $lines += (Get-Content $out -Raw) }
if (Test-Path $err) { $lines += "ERR:"; $lines += (Get-Content $err -Raw) }

$lines -join "`r`n" | Set-Content $report -Encoding utf8
Write-Output "wrote $report"
Get-Content $report
