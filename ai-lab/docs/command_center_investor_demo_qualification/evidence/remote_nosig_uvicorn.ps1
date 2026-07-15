$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot

Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $_.Id)).CommandLine
    if ($cl -and ($cl -match 'uvicorn|worker_assistant|serve_fix|uv_selector|boot_uvicorn|nosig')) {
      Stop-Process -Id $_.Id -Force -EA SilentlyContinue
    }
  } catch {}
}
Start-Sleep 2

$pyCode = @'
import asyncio, sys
print("start", flush=True)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import uvicorn
config = uvicorn.Config(
    "worker_assistant.app.main:app",
    host="0.0.0.0",
    port=8765,
    log_level="info",
    loop="asyncio",
)
server = uvicorn.Server(config)
server.install_signal_handlers = False
print("run_no_signals", flush=True)
server.run()
'@
Set-Content "$logDir\nosig_uvicorn.py" $pyCode -Encoding ascii
Remove-Item "$logDir\nosig.out","$logDir\nosig.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\nosig_uvicorn.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\nosig.out" -RedirectStandardError "$logDir\nosig.err"
Start-Sleep 10
$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
$lines += "OUT=$(Get-Content $logDir\nosig.out -Raw -EA SilentlyContinue)"
$lines += "ERR=$(Get-Content $logDir\nosig.err -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 4
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
$lines -join "`r`n" | Set-Content "$logDir\nosig_report.txt"
Get-Content "$logDir\nosig_report.txt"
