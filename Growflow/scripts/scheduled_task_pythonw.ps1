$ErrorActionPreference = "Stop"

function Resolve-GrowflowPythonw {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    $venvPythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
    if (Test-Path $venvPythonw) {
        return $venvPythonw
    }

    $pythonw = Get-Command "pythonw.exe" -ErrorAction SilentlyContinue
    if ($pythonw) {
        return $pythonw.Source
    }

    $python = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    throw "Could not find pythonw.exe or python.exe on PATH"
}

function ConvertTo-GrowflowTaskArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -match '\s') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function New-GrowflowPythonwTaskAction {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$RelativeScript,

        [string[]]$ScriptArgs = @()
    )

    $pythonw = Resolve-GrowflowPythonw -Root $Root
    $scriptPath = Join-Path $Root $RelativeScript
    if (-not (Test-Path $scriptPath)) {
        throw "Scheduled task script not found: $scriptPath"
    }

    $args = @((ConvertTo-GrowflowTaskArgument $scriptPath))
    foreach ($arg in $ScriptArgs) {
        $args += ConvertTo-GrowflowTaskArgument $arg
    }

    return New-ScheduledTaskAction `
        -Execute $pythonw `
        -Argument ($args -join " ") `
        -WorkingDirectory $Root
}
