param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$RelativeScript,

    [Parameter(ValueFromRemainingArguments = $true, Position = 1)]
    [string[]]$ScriptArgs
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONPATH = $root.Path

function Resolve-GrowflowPython {
    $venvPythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
    if (Test-Path $venvPythonw) {
        return $venvPythonw
    }

    $venvPython = Join-Path $root ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($pythonw) {
        return $pythonw.Source
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }

    throw "Could not find pythonw.exe, python.exe, or py.exe"
}

function Join-GrowflowProcessArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Parts
    )

    $quoted = foreach ($part in $Parts) {
        '"' + $part.Replace('"', '\"') + '"'
    }

    return ($quoted -join " ")
}

$scriptPath = Join-Path $root $RelativeScript
if (-not (Test-Path $scriptPath)) {
    throw "Script not found: $scriptPath"
}

$python = Resolve-GrowflowPython
$argsForPython = @($scriptPath) + @($ScriptArgs)

if ([System.IO.Path]::GetFileName($python).Equals("py.exe", [System.StringComparison]::OrdinalIgnoreCase)) {
    $argsForPython = @("-3") + $argsForPython
}

$process = Start-Process `
    -FilePath $python `
    -ArgumentList (Join-GrowflowProcessArgument -Parts $argsForPython) `
    -WorkingDirectory $root.Path `
    -WindowStyle Hidden `
    -Wait `
    -PassThru

exit $process.ExitCode
