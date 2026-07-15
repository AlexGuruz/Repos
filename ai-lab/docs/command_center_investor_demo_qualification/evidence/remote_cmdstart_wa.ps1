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
    if ($cl -and ($cl -match 'uvicorn|wa_serve|minimal|import_step|nosig')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2

$imp = @'
import sys
print("s1", flush=True)
from worker_assistant.app import main as m
print("s2", m.app.title, flush=True)
'@
Set-Content "$logDir\import_step.py" $imp -Encoding ascii
Remove-Item "$logDir\imp.out","$logDir\imp.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\import_step.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\imp.out" -RedirectStandardError "$logDir\imp.err"
Wait-Process -Id $p.Id -TimeoutSec 60 -ErrorAction SilentlyContinue
$lines = @("import_exited=$($p.HasExited) code=$($p.ExitCode)")
$lines += "OUT=$(Get-Content $logDir\imp.out -Raw -EA SilentlyContinue)"
$lines += "ERR=$(Get-Content $logDir\imp.err -Raw -EA SilentlyContinue)"

# Serve using interactive-style cmd start /B (no RedirectStandard* on Start-Process)
$serve = Join-Path $logDir "wa_serve.py"
@"
import asyncio, sys
print('wa_boot', flush=True)
async def main():
    import uvicorn
    from worker_assistant.app.main import app
    print('app_loaded', app.title, flush=True)
    config = uvicorn.Config(app, host='0.0.0.0', port=8765, log_level='info', loop='asyncio')
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print('serving', flush=True)
    await server.serve()
asyncio.run(main())
"@ | Set-Content $serve -Encoding ascii

Remove-Item "$logDir\api.log","$logDir\api.log.err" -Force -EA SilentlyContinue
$cmd = "set PYTHONPATH=$RepoRoot&& set PYTHONUNBUFFERED=1&& cd /d $RepoRoot&& `"$py`" -u `"$serve`" >> `"$logDir\api.log`" 2>>&1"
cmd.exe /c "start `"WorkerAssistant`" /MIN cmd.exe /c `"$cmd`""
Start-Sleep 12
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$lines += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
$lines += "LOG=$(Get-Content $logDir\api.log -Raw -EA SilentlyContinue)"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($h.StatusCode) $($h.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }
$lines -join "`r`n" | Set-Content "$logDir\cmdstart_report.txt"
Get-Content "$logDir\cmdstart_report.txt"
