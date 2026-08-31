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
    if ($cl -and ($cl -match 'uvicorn|nosig|minimal|serve_fix')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2

# A) TestClient health
$tc = & $py -c "from starlette.testclient import TestClient; from worker_assistant.app.main import app; c=TestClient(app); r=c.get('/health'); print(r.status_code, r.text)" 2>&1
"TESTCLIENT=$tc" | Set-Content "$logDir\min_report.txt"

# B) Minimal ASGI on 8765 with asyncio.start_server style via uvicorn Config(app object)
$min = @'
import asyncio, sys
print("m1", flush=True)

async def app(scope, receive, send):
    if scope["type"] != "http":
        return
    await send({"type":"http.response.start","status":200,"headers":[[b"content-type",b"application/json"]]})
    await send({"type":"http.response.body","body":b'{"ok":true,"minimal":true}'})

async def main():
    print("m2", flush=True)
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="debug")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    print("m3 serve", flush=True)
    await server.serve()

asyncio.run(main())
'@
Set-Content "$logDir\minimal_asgi.py" $min -Encoding ascii
Remove-Item "$logDir\min.out","$logDir\min.err" -Force -EA SilentlyContinue
$p = Start-Process $py -ArgumentList "$logDir\minimal_asgi.py" -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\min.out" -RedirectStandardError "$logDir\min.err"
Start-Sleep 8
Add-Content "$logDir\min_report.txt" "min_pid=$($p.Id) exited=$($p.HasExited)"
Add-Content "$logDir\min_report.txt" "OUT=$(Get-Content $logDir\min.out -Raw -EA SilentlyContinue)"
Add-Content "$logDir\min_report.txt" "ERR=$(Get-Content $logDir\min.err -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
Add-Content "$logDir\min_report.txt" "listen=$(if ($tcp) { $tcp.OwningProcess } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 3
  Add-Content "$logDir\min_report.txt" "health=$($h.StatusCode) $($h.Content)"
} catch { Add-Content "$logDir\min_report.txt" "health_err=$($_.Exception.Message)" }
Get-Content "$logDir\min_report.txt"
