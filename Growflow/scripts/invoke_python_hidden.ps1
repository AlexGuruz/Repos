param(
    [Parameter(Mandatory = $true)]
    [string]$RelativeScript,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path
if (-not $env:GROWFLOW_RETAIL_ORG) { $env:GROWFLOW_RETAIL_ORG = "nugzdispensary" }

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    throw "python.exe not found on PATH"
}
$pythonw = Join-Path (Split-Path $python -Parent) "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$script = $RelativeScript
if (-not [System.IO.Path]::IsPathRooted($script)) {
    $script = Join-Path $root $RelativeScript
}
if (-not (Test-Path $script)) {
    throw "Python script not found: $script"
}

$arguments = @("`"$script`"") + $ScriptArgs
$proc = Start-Process -FilePath $pythonw `
    -ArgumentList $arguments `
    -WorkingDirectory $root.Path `
    -WindowStyle Hidden `
    -Wait `
    -PassThru
exit $proc.ExitCode
