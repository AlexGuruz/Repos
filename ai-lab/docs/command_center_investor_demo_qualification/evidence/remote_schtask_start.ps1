$ErrorActionPreference = "Continue"
$RepoRoot = "C:\worker\worker_ai"
$logDir = "C:\worker\logs\worker_assistant"
$py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$serve = Join-Path $logDir "wa_serve.py"

# ensure serve script with file trace (app first)
@'
def log(msg):
    with open(r"C:\worker\logs\worker_assistant\trace.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n"); f.flush()
log("wa_boot")
from worker_assistant.app import main as wa_main
app = wa_main.app
log("app_loaded " + str(app.title))
import asyncio, uvicorn
log("imports_ok")
async def main():
    log("main_enter")
    config = uvicorn.Config(app, host="0.0.0.0", port=8765, log_level="info", loop="asyncio", lifespan="off")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    log("serving")
    await server.serve()
asyncio.run(main())
'@ | Set-Content $serve -Encoding ascii

Remove-Item "$logDir\trace.txt" -Force -EA SilentlyContinue
Get-Process python,pythonw -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 2

$taskName = "AiLabWorkerAssistantOnce"
schtasks /Delete /TN $taskName /F 2>$null | Out-Null
$tr = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `"$env:PYTHONPATH='$RepoRoot'; $env:PYTHONUNBUFFERED='1'; Set-Location '$RepoRoot'; Start-Process -FilePath '$py' -ArgumentList '-u','$serve' -WorkingDirectory '$RepoRoot' -WindowStyle Hidden`""
# Simpler action: run python directly
$action = New-ScheduledTaskAction -Execute $py -Argument "-u `"$serve`"" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(8)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
try {
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
} catch {
  # fallback without principal
  Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
}
# also inject env via wrapper
$wrap = Join-Path $logDir "schtask_wrap.ps1"
@"
`$env:PYTHONPATH = '$RepoRoot'
`$env:PYTHONUNBUFFERED = '1'
Set-Location '$RepoRoot'
& '$py' -u '$serve'
"@ | Set-Content $wrap -Encoding ascii
$action2 = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrap`""
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action2 -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-Sleep 15
$out = @()
$out += "task=$( (Get-ScheduledTask -TaskName $taskName).State )"
$out += "TRACE=$(Get-Content $logDir\trace.txt -Raw -EA SilentlyContinue)"
$tcp = Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue
$out += "listen=$(if ($tcp) { ($tcp | ForEach-Object OwningProcess) -join ',' } else { 'none' })"
try {
  $h = Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 5
  $out += "health=$($h.StatusCode) $($h.Content)"
} catch { $out += "health_err=$($_.Exception.Message)" }
$out -join "`r`n" | Set-Content "$logDir\schtask_report.txt"
Get-Content "$logDir\schtask_report.txt"
