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
    if ($cl -and ($cl -match 'uvicorn|worker_assistant|boot_uvicorn|http.server|bindtest')) {
      Stop-Process -Id $_.Id -Force -EA SilentlyContinue
    }
  } catch {}
}
Start-Sleep 2

# 1) Plain socket bind test
$bindPy = @'
import socket, time
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", 8765))
s.listen(5)
print("BOUND", flush=True)
time.sleep(20)
'@
Set-Content "$logDir\bindtest.py" $bindPy -Encoding ascii
$p1 = Start-Process $py -ArgumentList "$logDir\bindtest.py" -WindowStyle Hidden -PassThru -RedirectStandardOutput "$logDir\bind.out" -RedirectStandardError "$logDir\bind.err"
Start-Sleep 3
$r1 = @("bind_pid=$($p1.Id) exited=$($p1.HasExited)")
$r1 += "bind_out=$(Get-Content $logDir\bind.out -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$r1 += "bind_listen=$(if ($tcp) { $tcp.OwningProcess } else { 'none' })"
Stop-Process -Id $p1.Id -Force -EA SilentlyContinue
Start-Sleep 2

# 2) uvicorn with SelectorEventLoop policy (Windows hang workaround)
$uv = @'
import asyncio, sys, traceback
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
print("policy_set", flush=True)
import uvicorn
config = uvicorn.Config("worker_assistant.app.main:app", host="127.0.0.1", port=8765, log_level="info", loop="asyncio")
server = uvicorn.Server(config)
print("running", flush=True)
server.run()
'@
Set-Content "$logDir\uv_selector.py" $uv -Encoding ascii
Remove-Item "$logDir\uvsel.out","$logDir\uvsel.err" -Force -EA SilentlyContinue
$p2 = Start-Process $py -ArgumentList "$logDir\uv_selector.py" -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\uvsel.out" -RedirectStandardError "$logDir\uvsel.err"
Start-Sleep 10
$r1 += "uv_pid=$($p2.Id) exited=$($p2.HasExited)"
$r1 += "uv_out=$(Get-Content $logDir\uvsel.out -Raw -EA SilentlyContinue)"
$r1 += "uv_err=$(Get-Content $logDir\uvsel.err -Raw -EA SilentlyContinue)"
$tcp2 = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$r1 += "uv_listen=$(if ($tcp2) { $tcp2.OwningProcess } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 3
  $r1 += "health=$($h.StatusCode) $($h.Content)"
} catch { $r1 += "health_err=$($_.Exception.Message)" }

$r1 -join "`r`n" | Set-Content "$logDir\selector_report.txt"
Get-Content "$logDir\selector_report.txt"
