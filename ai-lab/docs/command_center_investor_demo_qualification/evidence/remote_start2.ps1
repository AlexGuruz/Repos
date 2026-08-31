$ErrorActionPreference = "Continue"
Set-Location C:\worker\worker_ai
$env:PYTHONPATH = "C:\worker\worker_ai"
$py = "C:\worker\worker_ai\.venv\Scripts\python.exe"
$out = "C:\worker\logs\worker_assistant\fg.out"
$err = "C:\worker\logs\worker_assistant\fg.err"
Remove-Item $out,$err -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $py -ArgumentList "-m","uvicorn","worker_assistant.app.main:app","--host","127.0.0.1","--port","8765" -WorkingDirectory "C:\worker\worker_ai" -PassThru -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden
Start-Sleep -Seconds 8
"pid=$($p.Id) exited=$($p.HasExited)" | Set-Content C:\worker\logs\worker_assistant\fg_status.txt
if (Test-Path $err) { Get-Content $err -Raw | Set-Content C:\worker\logs\worker_assistant\fg_err_copy.txt }
try { (Invoke-WebRequest http://127.0.0.1:8765/health -UseBasicParsing -TimeoutSec 3).Content | Set-Content C:\worker\logs\worker_assistant\fg_health.txt } catch { $_.Exception.Message | Set-Content C:\worker\logs\worker_assistant\fg_health.txt }
