param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$RelativeScript,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs = @()
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "scheduled_task_pythonw.ps1")

$pythonw = Resolve-GrowflowPythonw -Root $root.Path
$scriptPath = Join-Path $root.Path $RelativeScript
if (-not (Test-Path $scriptPath)) {
    throw "Python script not found: $scriptPath"
}

$args = @($scriptPath) + $ScriptArgs
$proc = Start-Process `
    -FilePath $pythonw `
    -ArgumentList $args `
    -WorkingDirectory $root.Path `
    -WindowStyle Hidden `
    -Wait `
    -PassThru

exit $proc.ExitCode
