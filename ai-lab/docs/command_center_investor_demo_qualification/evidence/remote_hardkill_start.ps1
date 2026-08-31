$ErrorActionPreference = "Continue"
$logDir = "C:\worker\logs\worker_assistant"
$RepoRoot = "C:\worker\worker_ai"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = $RepoRoot
$env:PYTHONUNBUFFERED = "1"

# Hard stop all python (worker-node dedicated to worker services per ops notes)
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 3
Remove-Item "$logDir\trace.txt" -Force -EA SilentlyContinue

Set-Location $RepoRoot
$p = Start-Process -FilePath $py -ArgumentList @("-u", "$logDir\wa_serve.py") -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru
Start-Sleep 20
$out = @("pid=$($p.Id) exited=$($p.HasExited)")
$out += "TRACE=$(Get-Content $logDir\trace.txt -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$out += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $out += "health=$($h.StatusCode) $($h.Content)"
} catch { $out += "health_err=$($_.Exception.Message)" }
$out -join "`r`n" | Set-Content "$logDir\hardkill_report.txt"
Get-Content "$logDir\hardkill_report.txt"
