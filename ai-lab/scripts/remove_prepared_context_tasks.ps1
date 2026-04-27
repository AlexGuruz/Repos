param()

$ErrorActionPreference = "Stop"

$names = @(
  "AI-Lab PreparedContext Worker",
  "AI-Lab PreparedContext System",
  "AI-Lab PreparedContext RepoPulse",
  "AI-Lab PreparedContext ProjectAgenda",
  "AI-Lab PreparedContext PersonalOps",
  "AI-Lab PreparedContext Growflow"
)

foreach ($n in $names) {
  $cmd = "schtasks /Delete /F /TN `"$n`""
  Write-Host "Running: $cmd"
  try {
    Invoke-Expression $cmd
  } catch {
    Write-Host "Skipped/failed: $n -> $($_.Exception.Message)"
  }
}

