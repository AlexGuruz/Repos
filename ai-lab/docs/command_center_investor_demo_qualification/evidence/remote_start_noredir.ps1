$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"
Set-Location $RepoRoot

# nuke python uvicorn procs carefully
Get-Process python -ErrorAction SilentlyContinue | ForEach-Object {
  try {
    $cl = (Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $_.Id)).CommandLine
    if ($cl -and ($cl -match 'uvicorn|worker_assistant')) {
      Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
  } catch {}
}
Start-Sleep 2
Remove-Item "$logDir\api.log","$logDir\api.log.err","$logDir\direct.out","$logDir\direct.err" -Force -ErrorAction SilentlyContinue

# Launch WITHOUT stdout redirect (Windows pipe hang workaround); ask uvicorn to write access log
$args = @(
  "-u","-m","uvicorn","worker_assistant.app.main:app",
  "--host","0.0.0.0","--port","8765",
  "--log-level","info"
)
$p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
"pid=$($p.Id)" | Set-Content "$logDir\direct_pid.txt"
Start-Sleep 8

$lines = @("pid=$($p.Id) exited=$($p.HasExited)")
try {
  $tcp = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue
  foreach ($t in @($tcp)) { $lines += "tcp state=$($t.State) addr=$($t.LocalAddress) pid=$($t.OwningProcess)" }
} catch { $lines += "tcp_err=$($_.Exception.Message)" }

try {
  $r = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $lines += "health=$($r.StatusCode) $($r.Content)"
} catch { $lines += "health_err=$($_.Exception.Message)" }

# Also try binding test in-process with hypercorn? Just dump uvicorn help
$help = & $py -c "import uvicorn; print('uvicorn', uvicorn.__version__)" 2>&1
$lines += "uvicorn=$help"

# Check if port blocked by Hyper-V reserved ranges
$lines += "excluded="
$lines += (netsh interface ipv4 show excludedportrange protocol=tcp | Out-String)

$lines -join "`r`n" | Set-Content "$logDir\direct_report.txt" -Encoding utf8
Get-Content "$logDir\direct_report.txt"
