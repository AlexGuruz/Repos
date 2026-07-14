# Invoke a repo-relative Python script through pythonw.exe when available.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$RelativeScript,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
if (-not $env:GROWFLOW_RETAIL_ORG) { $env:GROWFLOW_RETAIL_ORG = "nugzdispensary" }

$python = (Get-Command python -ErrorAction Stop).Source
$pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$script = Join-Path $root $RelativeScript
if (-not (Test-Path $script)) {
    throw "Missing Python script: $script"
}

$argsForPython = @($script) + @($ScriptArgs)
$proc = Start-Process `
    -FilePath $pythonw `
    -ArgumentList $argsForPython `
    -WorkingDirectory $root.Path `
    -WindowStyle Hidden `
    -Wait `
    -PassThru

exit $proc.ExitCode
