$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot

# Kill uvicorn
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $_.Id)).CommandLine
    if ($cl -and ($cl -match 'uvicorn|worker_assistant')) { Stop-Process -Id $_.Id -Force -EA SilentlyContinue }
  } catch {}
}
Start-Sleep 2

$script = @'
import sys, traceback
print("boot1", flush=True)
try:
    import uvicorn
    print("boot2 uvicorn", uvicorn.__version__, flush=True)
    print("boot3 creating config", flush=True)
    config = uvicorn.Config("worker_assistant.app.main:app", host="127.0.0.1", port=8765, log_level="info")
    print("boot4 Server", flush=True)
    server = uvicorn.Server(config)
    print("boot5 run", flush=True)
    server.run()
except Exception:
    traceback.print_exc()
    sys.exit(2)
'@
$path = Join-Path $logDir "boot_uvicorn.py"
Set-Content -Path $path -Value $script -Encoding ascii
Remove-Item "$logDir\boot.out","$logDir\boot.err" -Force -EA SilentlyContinue
$p = Start-Process -FilePath $py -ArgumentList @($path) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru `
  -RedirectStandardOutput "$logDir\boot.out" -RedirectStandardError "$logDir\boot.err"
Start-Sleep 12
$report = @("pid=$($p.Id) exited=$($p.HasExited)")
$report += "OUT=$(if (Test-Path $logDir\boot.out) { Get-Content $logDir\boot.out -Raw } else { 'missing' })"
$report += "ERR=$(if (Test-Path $logDir\boot.err) { Get-Content $logDir\boot.err -Raw } else { 'missing' })"
$tcp = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
$report += "tcp=$(if ($tcp) { ($tcp | ForEach-Object { \"$($_.State):$($_.OwningProcess)\" }) -join ',' } else { 'none' })"
$report -join "`r`n" | Set-Content "$logDir\boot_report.txt"
Get-Content "$logDir\boot_report.txt"
