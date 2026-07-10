param(
  [string]$PythonExe = "python",
  [string]$AiLabRoot = "E:/Repos/ai-lab",
  [switch]$Apply,
  [switch]$RunInitialBuild = $true
)

$ErrorActionPreference = "Stop"

function New-TaskCommand {
  param(
    [string]$TaskName,
    [string]$Schedule,
    [string]$Modifier,
    [string]$ScriptPath
  )
  $quotedTask = '"' + $TaskName + '"'
  $quotedTr = '"' + "$PythonExe `"$AiLabRoot/scripts/build_prepared_context.py`" --snapshot $ScriptPath" + '"'
  $cmd = "schtasks /Create /F /TN $quotedTask /TR $quotedTr /SC $Schedule"
  if ($Modifier) {
    $cmd += " /MO $Modifier"
  }
  return $cmd
}

$tasks = @(
  @{ Name = "AI-Lab PreparedContext Worker";        Schedule = "MINUTE"; Modifier = "10"; Script = "worker_snapshot" },
  @{ Name = "AI-Lab PreparedContext System";        Schedule = "MINUTE"; Modifier = "15"; Script = "system_snapshot" },
  @{ Name = "AI-Lab PreparedContext RepoPulse";     Schedule = "MINUTE"; Modifier = "45"; Script = "repo_pulse" },
  @{ Name = "AI-Lab PreparedContext ProjectAgenda"; Schedule = "DAILY";  Modifier = "";   Script = "project_agenda" },
  @{ Name = "AI-Lab PreparedContext PersonalOps";   Schedule = "DAILY";  Modifier = "";   Script = "personal_ops_snapshot" },
  @{ Name = "AI-Lab PreparedContext Growflow";      Schedule = "MINUTE"; Modifier = "60"; Script = "growflow_snapshot" }
)

Write-Host "Prepared-context task plan:"
foreach ($t in $tasks) {
  $cmd = New-TaskCommand -TaskName $t.Name -Schedule $t.Schedule -Modifier $t.Modifier -ScriptPath $t.Script
  Write-Host " - $cmd"
  if ($Apply) {
    Write-Host "   applying..."
    Invoke-Expression $cmd
  }
}

if (-not $Apply) {
  Write-Host ""
  Write-Host "Dry-run only. Re-run with -Apply to create/update tasks."
} elseif ($RunInitialBuild) {
  $buildCmd = "$PythonExe `"$AiLabRoot/scripts/build_prepared_context.py`" --snapshot all"
  Write-Host ""
  Write-Host "Running initial all-snapshot build: $buildCmd"
  Invoke-Expression $buildCmd
}

