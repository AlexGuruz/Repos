param(
  [int]$IntervalSeconds = 300
)

Set-Location "D:\Project-Kylo"
$env:KYLO_WATCH_INTERVAL_SECS = "$IntervalSeconds"

$logDir = ".\.kylo"
$logPath = "$logDir\watch.log"
if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

Write-Host "Watcher starting (interval=$IntervalSeconds s). Logging to $logPath"
python -m bin.watch_all | Tee-Object -FilePath $logPath -Append


